"""Capability-based application effect execution and final CAN rate policy."""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, assert_never

from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    ApplicationEffect,
    SetButtonLeds,
    SetHighBeam,
    SetSteeringAssistance,
)
from e87canbus.can_io import CanTransmitter
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendRegistryFrame:
    """A typed raw CAN effect executed through the normal network TX policy."""

    routed: RoutedCanFrame


OutputEffect = ApplicationEffect | SendRegistryFrame


@dataclass(frozen=True)
class EffectRequest:
    """An effect plus the optional originating button for synchronous failures."""

    effect: OutputEffect
    origin_button_index: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.effect,
            (SetButtonLeds, SetSteeringAssistance, SetHighBeam, SendRegistryFrame),
        ):
            raise ValueError("effect request must contain an executable effect")
        if self.origin_button_index is not None and (
            type(self.origin_button_index) is not int
            or not 0 <= self.origin_button_index < BUTTON_LED_COUNT
        ):
            raise ValueError("effect origin must identify a button LED")
        if isinstance(self.effect, SetSteeringAssistance) and not math.isfinite(
            self.effect.assistance
        ):
            raise ValueError("steering assistance must be finite")


@dataclass(frozen=True)
class CanEffectFailure:
    network: CanNetwork
    message: str
    origin_button_index: int | None = None


@dataclass(frozen=True)
class SteeringActuatorFailure:
    message: str
    origin_button_index: int | None = None


@dataclass(frozen=True)
class HighBeamActuatorFailure:
    message: str
    origin_button_index: int | None = None


EffectFailure = CanEffectFailure | SteeringActuatorFailure | HighBeamActuatorFailure


class SteeringActuator(Protocol):
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        """Apply one already-selected, dimensionless assistance command."""


class HighBeamActuator(Protocol):
    """Explicit output capability; live composition intentionally does not provide one."""

    def set_high_beam(self, command: SetHighBeam) -> None:
        """Apply one protocol-independent high-beam request."""


class SafeCanTransmitter:
    """The only coordinator CAN write capability, enforcing the network window."""

    def __init__(
        self,
        transmitter: CanTransmitter,
        policy: TxPolicyConfig,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transmitter = transmitter
        self._policy = policy
        self._clock = clock
        self._network_send_times: deque[float] = deque()

    def send(self, frame: CanFrame) -> bool:
        now = self._clock()
        _discard_expired(
            self._network_send_times,
            now - self._policy.network_window_s,
        )
        if len(self._network_send_times) >= self._policy.max_frames_per_network_window:
            LOGGER.warning(
                "dropped rate-limited CAN frame: id=0x%03x reason=network-window",
                frame.arbitration_id,
            )
            return False

        # Reserve the budget before I/O: a failed send has an uncertain bus outcome and must
        # not permit an unbounded retry loop.
        self._network_send_times.append(now)
        self._transmitter.send(frame)
        return True


class EffectExecutor:
    """Route and execute ordered effects using only explicitly granted capabilities."""

    def __init__(
        self,
        transmitters: Mapping[CanNetwork, SafeCanTransmitter] | None = None,
        router: ProtocolRouter | None = None,
        steering_actuator: SteeringActuator | None = None,
        high_beam_actuator: HighBeamActuator | None = None,
    ) -> None:
        self._transmitters = dict(transmitters or {})
        self._router = router or ProtocolRouter()
        self._steering_actuator = steering_actuator
        self._high_beam_actuator = high_beam_actuator

    def execute(
        self,
        effects: tuple[EffectRequest, ...],
    ) -> tuple[EffectFailure, ...]:
        failures: list[EffectFailure] = []
        for request in effects:
            if not isinstance(request, EffectRequest):
                raise TypeError("EffectExecutor accepts only EffectRequest values")
            effect = request.effect
            origin_button_index = request.origin_button_index
            match effect:
                case SetSteeringAssistance():
                    steering_failure = self._execute_steering(effect, origin_button_index)
                    if steering_failure is not None:
                        failures.append(steering_failure)
                case SetButtonLeds():
                    can_failure = self._execute_can(effect, origin_button_index)
                    if can_failure is not None:
                        failures.append(can_failure)
                case SetHighBeam():
                    high_beam_failure = self._execute_high_beam(effect, origin_button_index)
                    if high_beam_failure is not None:
                        failures.append(high_beam_failure)
                case SendRegistryFrame():
                    can_failure = self._execute_routed_can(effect, origin_button_index)
                    if can_failure is not None:
                        failures.append(can_failure)
                case _:
                    assert_never(effect)
        return tuple(failures)

    def _execute_can(
        self,
        effect: SetButtonLeds,
        origin_button_index: int | None,
    ) -> CanEffectFailure | None:
        routed = self._router.encode(effect)
        return self._execute_routed_can(
            SendRegistryFrame(routed),
            origin_button_index,
            log_unavailable_tx=True,
        )

    def _execute_routed_can(
        self,
        effect: SendRegistryFrame,
        origin_button_index: int | None,
        *,
        log_unavailable_tx: bool = False,
    ) -> CanEffectFailure | None:
        routed = effect.routed
        transmitter = self._transmitters.get(routed.network)
        if transmitter is None:
            if log_unavailable_tx:
                LOGGER.warning(
                    "dropped effect for unavailable TX capability: network=%s id=0x%03x",
                    routed.network.value,
                    routed.frame.arbitration_id,
                )
            return None
        try:
            transmitter.send(routed.frame)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning(
                "failed to execute effect: network=%s id=0x%03x error=%s",
                routed.network.value,
                routed.frame.arbitration_id,
                exc,
            )
            return CanEffectFailure(routed.network, str(exc), origin_button_index)
        return None

    def _execute_steering(
        self,
        command: SetSteeringAssistance,
        origin_button_index: int | None,
    ) -> SteeringActuatorFailure | None:
        if self._steering_actuator is None:
            return None
        try:
            self._steering_actuator.set_assistance(command)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("failed to execute steering effect: error=%s", exc)
            return SteeringActuatorFailure(str(exc), origin_button_index)
        return None

    def _execute_high_beam(
        self,
        command: SetHighBeam,
        origin_button_index: int | None,
    ) -> HighBeamActuatorFailure | None:
        if self._high_beam_actuator is None:
            return None
        try:
            self._high_beam_actuator.set_high_beam(command)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("failed to execute high-beam effect: error=%s", exc)
            return HighBeamActuatorFailure(str(exc), origin_button_index)
        return None


def _discard_expired(send_times: deque[float], cutoff: float) -> None:
    while send_times and send_times[0] <= cutoff:
        send_times.popleft()
