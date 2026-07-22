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

from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    ApplicationEffect,
    ButtonFeedbackColour,
    ConfigureServotronicCurve,
    SetButtonPadBreathe,
    SetButtonPadProgram,
    SetHighBeam,
    SetSteeringAssistance,
    TriggerButtonPadBlink,
)
from e87canbus.button_pad import pack_button_pad_transfers
from e87canbus.can_io import CanTransmitter
from e87canbus.config import CanNetwork, TxPolicyConfig
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.generated import (
    BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE,
    BUTTON_PAD_EFFECT_BLINK_RED_DOUBLE,
    BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE,
    BUTTON_PAD_EFFECT_BREATHE,
    BUTTON_PAD_EFFECT_LENGTH,
)
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.servotronic_protocol import ServotronicStatus, pack_curve, unpack_status
from e87canbus.transport.isotp import IsoTpEndpoint

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
            (
                SetButtonPadProgram,
                TriggerButtonPadBlink,
                SetButtonPadBreathe,
                SetSteeringAssistance,
                ConfigureServotronicCurve,
                SetHighBeam,
                SendRegistryFrame,
            ),
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
        button_pad_payload_interval_s: float = 0.0,
    ) -> None:
        self._transmitters = dict(transmitters or {})
        self._router = router or ProtocolRouter()
        self._steering_actuator = steering_actuator
        self._high_beam_actuator = high_beam_actuator
        self._button_pad_effect_sequence = 0
        transmitter = self._transmitters.get(CanNetwork.KCAN)

        def send_transport_frame(frame: CanFrame) -> None:
            if transmitter is not None:
                transmitter.send(frame)

        self._button_pad_transport = (
            None
            if transmitter is None
            else IsoTpEndpoint(
                tx_id=self._router.ids.button_pad_transport_coordinator_to_device,
                rx_id=self._router.ids.button_pad_transport_device_to_coordinator,
                send_frame=send_transport_frame,
                maximum_payload_length=self._router.ids.button_pad_transport_maximum_payload_length,
                # Live hardware spaces command starts because each 16-byte command
                # occupies three classic CAN frames. Simulation may opt out.
                minimum_payload_interval_s=button_pad_payload_interval_s,
            )
        )
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
                case ConfigureServotronicCurve():
                    if self._servotronic_transport is not None:
                        try:
                            self._servotronic_transport.send(
                                pack_curve(effect.definition, effect.activation_revision)
                            )
                            self._servotronic_transport.poll()
                        except (OSError, RuntimeError, ValueError) as exc:
                            failures.append(
                                CanEffectFailure(CanNetwork.KCAN, str(exc), origin_button_index)
                            )
                case SetButtonPadProgram():
                    can_failure = self._execute_can(effect, origin_button_index)
                    if can_failure is not None:
                        failures.append(can_failure)
                case TriggerButtonPadBlink() | SetButtonPadBreathe():
                    can_failure = self._execute_button_pad_effect(effect, origin_button_index)
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

    def _execute_button_pad_effect(
        self,
        effect: TriggerButtonPadBlink | SetButtonPadBreathe,
        origin_button_index: int | None,
    ) -> CanEffectFailure | None:
        opcode = (
            {
                ButtonFeedbackColour.RED: BUTTON_PAD_EFFECT_BLINK_RED_DOUBLE,
                ButtonFeedbackColour.WHITE: BUTTON_PAD_EFFECT_BLINK_WHITE_SINGLE,
                ButtonFeedbackColour.AMBER: BUTTON_PAD_EFFECT_BLINK_AMBER_DOUBLE,
            }[effect.colour]
            if isinstance(effect, TriggerButtonPadBlink)
            else BUTTON_PAD_EFFECT_BREATHE
        )
        enabled = 1 if isinstance(effect, TriggerButtonPadBlink) or effect.enabled else 0
        payload = bytes(
            (1, opcode, effect.button_index, self._button_pad_effect_sequence, enabled, 0, 0, 0)
        )
        assert len(payload) == BUTTON_PAD_EFFECT_LENGTH
        self._button_pad_effect_sequence = (self._button_pad_effect_sequence + 1) & 0xFF
        return self._execute_routed_can(
            SendRegistryFrame(
                RoutedCanFrame(
                    CanNetwork.KCAN,
                    CanFrame(self._router.ids.button_pad_effect, payload),
                )
            ),
            origin_button_index,
        )

    def _execute_can(
        self,
        effect: SetButtonPadProgram,
        origin_button_index: int | None,
    ) -> CanEffectFailure | None:
        if self._button_pad_transport is None:
            LOGGER.warning("dropped button-pad RGB effect for unavailable TX capability")
            return None
        try:
            self._button_pad_transport.send_many(pack_button_pad_transfers(effect.program))
            self._button_pad_transport.poll()
        except (OSError, RuntimeError, ValueError) as exc:
            return CanEffectFailure(CanNetwork.KCAN, str(exc), origin_button_index)
        return None

    def poll_transport(self) -> None:
        """Advance the button-pad ISO-TP state machine on each service tick."""
        try:
            if self._button_pad_transport is not None:
                self._button_pad_transport.poll()
            if self._servotronic_transport is not None:
                self._servotronic_transport.poll()
                self._drain_servotronic_statuses()
        except (OSError, RuntimeError) as exc:
            LOGGER.warning("button-pad transport poll error: %s", exc)

    def on_frame(self, network: CanNetwork, frame: CanFrame) -> bool:
        if network is not CanNetwork.KCAN:
            return False
        accepted = False
        for transport in (self._button_pad_transport, self._servotronic_transport):
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
