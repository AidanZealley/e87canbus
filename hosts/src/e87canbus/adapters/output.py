"""Capability-based application effect execution and final CAN rate policy."""

from __future__ import annotations

import logging
import math
import struct
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, assert_never

from e87canbus.adapters.can_io import CanTransmitter
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.domain.events import (
    ApplicationEffect,
    ConfigureServotronicCurve,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.protocol.servotronic_protocol import (
    ControlMode,
    ServotronicStatus,
    pack_control,
    pack_curve,
    unpack_status,
)
from e87canbus.transport.isotp import IsoTpEndpoint

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendRegistryFrame:
    """A typed raw CAN effect executed through the normal network TX policy."""

    routed: RoutedCanFrame


OutputEffect = ApplicationEffect | SendRegistryFrame


@dataclass(frozen=True)
class EffectRequest:
    """An executable application effect."""

    effect: OutputEffect

    def __post_init__(self) -> None:
        if not isinstance(
            self.effect,
            (
                SetSteeringAssistance,
                ConfigureServotronicCurve,
                SendRegistryFrame,
            ),
        ):
            raise ValueError("effect request must contain an executable effect")
        if isinstance(self.effect, SetSteeringAssistance) and not math.isfinite(
            self.effect.assistance
        ):
            raise ValueError("steering assistance must be finite")


@dataclass(frozen=True)
class CanEffectFailure:
    network: CanNetwork
    message: str


@dataclass(frozen=True)
class SteeringActuatorFailure:
    message: str


EffectFailure = CanEffectFailure | SteeringActuatorFailure


class SteeringActuator(Protocol):
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        """Apply one already-selected, dimensionless assistance command."""


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
    ) -> None:
        self._transmitters = dict(transmitters or {})
        self._router = router or ProtocolRouter()
        self._steering_actuator = steering_actuator
        transmitter = self._transmitters.get(CanNetwork.KCAN)

        def send_transport_frame(frame: CanFrame) -> None:
            if transmitter is not None:
                transmitter.send(frame)

        self._servotronic_transport = (
            None
            if transmitter is None
            else IsoTpEndpoint(
                tx_id=self._router.ids.servotronic_transport_coordinator_to_device,
                rx_id=self._router.ids.servotronic_transport_device_to_coordinator,
                send_frame=send_transport_frame,
                maximum_payload_length=self._router.ids.servotronic_transport_maximum_payload_length,
            )
        )
        self._servotronic_statuses: deque[ServotronicStatus] = deque()

    def execute(
        self,
        effects: tuple[EffectRequest, ...],
    ) -> tuple[EffectFailure, ...]:
        failures: list[EffectFailure] = []
        servotronic_payloads: list[bytes] = []
        for request in effects:
            if not isinstance(request, EffectRequest):
                raise TypeError("EffectExecutor accepts only EffectRequest values")
            effect = request.effect
            match effect:
                case SetSteeringAssistance():
                    if self._steering_actuator is None:
                        if self._servotronic_transport is not None:
                            servotronic_payloads.append(_pack_steering_control(effect))
                    else:
                        steering_failure = self._execute_steering(effect)
                        if steering_failure is not None:
                            failures.append(steering_failure)
                case ConfigureServotronicCurve():
                    if self._servotronic_transport is not None:
                        servotronic_payloads.append(
                            pack_curve(effect.definition, effect.activation_revision)
                        )
                case SendRegistryFrame():
                    can_failure = self._execute_routed_can(effect)
                    if can_failure is not None:
                        failures.append(can_failure)
                case _:
                    assert_never(effect)
        if servotronic_payloads and self._servotronic_transport is not None:
            try:
                self._servotronic_transport.send_many(tuple(servotronic_payloads))
                self._servotronic_transport.poll()
            except (OSError, RuntimeError, ValueError) as exc:
                failures.append(CanEffectFailure(CanNetwork.KCAN, str(exc)))
        return tuple(failures)

    def poll_transport(self) -> None:
        """Advance the Servotronic ISO-TP state machine on each service tick."""
        try:
            if self._servotronic_transport is not None:
                self._servotronic_transport.poll()
                self._drain_servotronic_statuses()
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("Servotronic transport poll error: %s", exc)

    def on_frame(self, network: CanNetwork, frame: CanFrame) -> bool:
        if network is not CanNetwork.KCAN:
            return False
        accepted = False
        for transport in (self._servotronic_transport,):
            if transport is not None and transport.on_frame(frame):
                transport.poll()
                accepted = True
        self._drain_servotronic_statuses()
        return accepted

    def _drain_servotronic_statuses(self) -> None:
        if self._servotronic_transport is None:
            return
        while (payload := self._servotronic_transport.receive_payload()) is not None:
            try:
                self._servotronic_statuses.append(unpack_status(payload))
            except (ValueError, struct.error):
                LOGGER.warning("ignored malformed Servotronic status payload")

    def take_servotronic_statuses(self) -> tuple[ServotronicStatus, ...]:
        statuses = tuple(self._servotronic_statuses)
        self._servotronic_statuses.clear()
        return statuses

    def _execute_routed_can(
        self,
        effect: SendRegistryFrame,
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
            return CanEffectFailure(routed.network, str(exc))
        return None

    def _execute_steering(
        self,
        command: SetSteeringAssistance,
    ) -> SteeringActuatorFailure | None:
        if self._steering_actuator is None:
            return None
        try:
            self._steering_actuator.set_assistance(command)
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("failed to execute steering effect: error=%s", exc)
            return SteeringActuatorFailure(str(exc))
        return None


def _pack_steering_control(command: SetSteeringAssistance) -> bytes:
    mode = (
        ControlMode.MANUAL
        if command.reason is SteeringCommandReason.MANUAL
        else ControlMode.MAXIMUM
        if command.reason is SteeringCommandReason.MAXIMUM
        else ControlMode.AUTO
    )
    return pack_control(command.assistance, mode)


def _discard_expired(send_times: deque[float], cutoff: float) -> None:
    while send_times and send_times[0] <= cutoff:
        send_times.popleft()
