"""Simulated project CAN devices."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    RGB_OFF,
    SetHighBeam,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.can_io import CanEndpoint
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.device import DeviceRole
from e87canbus.output import SafeCanTransmitter
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    DeviceWelcomeAckPayload,
    RgbSnapshotPayload,
    decode_rgb_snapshot,
    decode_welcome_ack,
    encode_button_event,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.simulation.protocol import (
    SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID,
    decode_simulated_high_beam_command,
    decode_simulated_temperature,
    encode_simulated_coolant_temperature,
    encode_simulated_engine_rpm,
    encode_simulated_oil_temperature,
    encode_simulated_speed,
)
from e87canbus.transport.isotp import IsoTpEndpoint

LOGGER = logging.getLogger(__name__)

HELLO_CADENCE_S = 1.0
HEARTBEAT_CADENCE_S = 1.0
CONTACT_TIMEOUT_S = 3.0
INCOMPATIBLE_RETRY_S = 5.0


class SimulatedDeviceState(StrEnum):
    """Private device-local state; registry lifecycle remains kernel-owned."""

    BOOTING = "booting"
    DISCOVERING = "discovering"
    OPERATIONAL = "operational"
    INCOMPATIBLE = "incompatible"
    CONTROLLER_LOST = "controller_lost"
    LOCAL_FAULT = "local_fault"
    DISCONNECTED = "disconnected"


class SimulatedRegistryPeer:
    """A virtual device that speaks the real registry wire protocol."""

    def __init__(
        self,
        *,
        role: DeviceRole,
        bus: CanEndpoint | None,
        ids: CustomCanIds | None,
        clock: Callable[[], float],
    ) -> None:
        self.role = role
        self.bus = bus
        self.ids = ids or CustomCanIds()
        self.clock = clock
        self.device_id = 1
        self.protocol_version = 1
        self.status_code = 0
        self.connected = True
        self.session_id = 0
        self.hello_sequence = 0
        self.heartbeat_sequence = 0
        self.state = SimulatedDeviceState.BOOTING
        self.expected_controller_session_id: int | None = None
        self._last_sent_sequence: int | None = None
        self._next_hello_at: float | None = None
        self._next_heartbeat_at: float | None = None
        self._controller_lease_deadline: float | None = None
        self._start_session()

    @property
    def next_deadline(self) -> float | None:
        deadlines = tuple(
            deadline
            for deadline in (
                self._next_hello_at,
                self._next_heartbeat_at,
                self._controller_lease_deadline,
            )
            if deadline is not None
        )
        return min(deadlines) if deadlines else None

    def configure_registry(self, bus: CanEndpoint, ids: CustomCanIds) -> None:
        """Attach the role's endpoint when a custom actuator factory is used."""

        self.bus = bus
        self.ids = ids

    def connect(self) -> bool:
        if self.connected:
            return False
        self.connected = True
        self._start_session()
        return True

    def disconnect(self) -> bool:
        if not self.connected:
            return False
        self.connected = False
        self.state = SimulatedDeviceState.DISCONNECTED
        self.expected_controller_session_id = None
        self._last_sent_sequence = None
        self._next_hello_at = None
        self._next_heartbeat_at = None
        self._controller_lease_deadline = None
        self._discard_pending_frames()
        return True

    def reboot(self) -> None:
        if not self.connected:
            raise RuntimeError("simulated device is disconnected")
        self._start_session()

    def set_protocol_version(self, version: int) -> None:
        _require_byte(version, "protocol_version")
        changed = version != self.protocol_version
        self.protocol_version = version
        if changed and self.connected:
            self.reboot()

    def set_status_code(self, status_code: int) -> None:
        _require_byte(status_code, "status_code")
        self.status_code = status_code
        if status_code != 0 and self.state is SimulatedDeviceState.OPERATIONAL:
            self.state = SimulatedDeviceState.LOCAL_FAULT

    def advance(self, now: float) -> int:
        """Send at most one due peer frame, keeping each scheduler step bounded."""

        if not self.connected or self.bus is None:
            return 0
        if not math.isfinite(now):
            raise ValueError("simulated device time must be finite")
        if (
            self._controller_lease_deadline is not None
            and now >= self._controller_lease_deadline
            and self.state
            in {
                SimulatedDeviceState.OPERATIONAL,
                SimulatedDeviceState.LOCAL_FAULT,
            }
        ):
            self.state = SimulatedDeviceState.CONTROLLER_LOST
            self.expected_controller_session_id = None
            self._next_heartbeat_at = None
            self._controller_lease_deadline = None
            self._next_hello_at = now

        if self.state in {
            SimulatedDeviceState.DISCOVERING,
            SimulatedDeviceState.CONTROLLER_LOST,
            SimulatedDeviceState.INCOMPATIBLE,
        }:
            if self._next_hello_at is not None and now >= self._next_hello_at:
                self._send_hello()
                cadence = (
                    INCOMPATIBLE_RETRY_S
                    if self.state is SimulatedDeviceState.INCOMPATIBLE
                    else HELLO_CADENCE_S
                )
                self._next_hello_at = now + cadence
                return 1
            return 0

        if (
            self.state
            in {
                SimulatedDeviceState.OPERATIONAL,
                SimulatedDeviceState.LOCAL_FAULT,
            }
            and self._next_heartbeat_at is not None
            and now >= self._next_heartbeat_at
        ):
            self._send_heartbeat()
            self._next_heartbeat_at = now + HEARTBEAT_CADENCE_S
            return 1
        return 0

    def process_pending(self, now: float, *, limit: int = 64) -> int:
        if self.bus is None:
            return 0
        if limit < 1:
            raise ValueError("simulated device frame limit must be positive")
        processed = 0
        while processed < limit and (frame := self.bus.receive(timeout_s=0)) is not None:
            processed += 1
            self._consume_registry_frame(frame, now)
        return processed

    def _consume_registry_frame(self, frame: CanFrame, now: float) -> bool:
        if frame.arbitration_id != self._welcome_ack_id:
            return False
        try:
            acknowledgement = decode_welcome_ack(frame, self._welcome_ack_id)
        except ValueError as exc:
            LOGGER.warning(
                "simulated %s ignored malformed WELCOME_ACK: data=%s error=%s",
                self.role.value,
                frame.data.hex(),
                exc,
            )
            return True
        assert acknowledgement is not None
        if not self._acknowledgement_matches(acknowledgement):
            return True
        if acknowledgement.response_code == 1:
            self.state = SimulatedDeviceState.INCOMPATIBLE
            self.expected_controller_session_id = acknowledgement.controller_session_id
            self._next_hello_at = now + INCOMPATIBLE_RETRY_S
            self._next_heartbeat_at = None
            self._controller_lease_deadline = None
            return True
        if acknowledgement.controller_protocol_version != 1:
            return True
        was_operational = self.state in {
            SimulatedDeviceState.OPERATIONAL,
            SimulatedDeviceState.LOCAL_FAULT,
        }
        self.expected_controller_session_id = acknowledgement.controller_session_id
        self._controller_lease_deadline = now + CONTACT_TIMEOUT_S
        self._next_hello_at = None
        if not was_operational:
            self._next_heartbeat_at = now
        self.state = (
            SimulatedDeviceState.LOCAL_FAULT
            if self.status_code != 0
            else SimulatedDeviceState.OPERATIONAL
        )
        return True

    def _acknowledgement_matches(self, acknowledgement: DeviceWelcomeAckPayload) -> bool:
        if (
            acknowledgement.device_id != self.device_id
            or acknowledgement.device_session_id != self.session_id
            or acknowledgement.device_sequence != self._last_sent_sequence
        ):
            return False
        return self.expected_controller_session_id is None or (
            acknowledgement.controller_session_id == self.expected_controller_session_id
        )

    def _start_session(self) -> None:
        self.session_id = (self.session_id + 1) % 0x1_0000
        self.hello_sequence = 0
        self.heartbeat_sequence = 0
        self.state = SimulatedDeviceState.DISCOVERING
        self.expected_controller_session_id = None
        self._last_sent_sequence = None
        self._next_hello_at = self.clock()
        self._next_heartbeat_at = None
        self._controller_lease_deadline = None
        self._discard_pending_frames()

    def _send_hello(self) -> None:
        bus = self._require_bus()
        sequence = self.hello_sequence
        self._last_sent_sequence = sequence
        bus.send(
            encode_hello(
                DeviceHelloPayload(
                    protocol_version=self.protocol_version,
                    device_id=self.device_id,
                    device_session_id=self.session_id,
                    sequence=sequence,
                ),
                self._hello_id,
            )
        )
        self.hello_sequence = (self.hello_sequence + 1) % 256

    def _send_heartbeat(self) -> None:
        bus = self._require_bus()
        sequence = self.heartbeat_sequence
        self._last_sent_sequence = sequence
        bus.send(
            encode_heartbeat(
                DeviceHeartbeatPayload(
                    device_id=self.device_id,
                    device_session_id=self.session_id,
                    controller_session_id=self.expected_controller_session_id or 0,
                    sequence=sequence,
                    status=self.status_code,
                ),
                self._heartbeat_id,
            )
        )
        self.heartbeat_sequence = (self.heartbeat_sequence + 1) % 256

    @property
    def _hello_id(self) -> int:
        return (
            self.ids.button_pad_hello
            if self.role is DeviceRole.BUTTON_PAD
            else self.ids.servotronic_controller_hello
        )

    @property
    def _welcome_ack_id(self) -> int:
        return (
            self.ids.button_pad_welcome_ack
            if self.role is DeviceRole.BUTTON_PAD
            else self.ids.servotronic_controller_welcome_ack
        )

    @property
    def _heartbeat_id(self) -> int:
        return (
            self.ids.button_pad_heartbeat
            if self.role is DeviceRole.BUTTON_PAD
            else self.ids.servotronic_controller_heartbeat
        )

    def _discard_pending_frames(self) -> None:
        if self.bus is None:
            return
        while self.bus.receive(timeout_s=0) is not None:
            pass

    def _require_bus(self) -> CanEndpoint:
        if self.bus is None:
            raise RuntimeError(f"simulated {self.role.value} has no CAN endpoint")
        return self.bus


def _require_byte(value: int, name: str) -> None:
    if type(value) is not int or not 0 <= value <= 0xFF:
        raise ValueError(f"{name} must fit in an unsigned byte")


@dataclass(frozen=True)
class SimulatedHighBeamActuator:
    """Simulator-only high-beam capability using the private virtual-car frame."""

    transmitter: SafeCanTransmitter

    def set_high_beam(self, command: SetHighBeam) -> None:
        from e87canbus.simulation.protocol import encode_simulated_high_beam_command

        self.transmitter.send(encode_simulated_high_beam_command(command.enabled))


class SimulatedNeoTrellisNode(SimulatedRegistryPeer):
    """Simulation of the current Arduino NeoTrellis CAN firmware."""

    def __init__(
        self,
        bus: CanEndpoint,
        ids: CustomCanIds,
        led_rgb: tuple[tuple[int, int, int], ...] = (RGB_OFF,) * BUTTON_LED_COUNT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            role=DeviceRole.BUTTON_PAD,
            bus=bus,
            ids=ids,
            clock=clock,
        )
        self.led_rgb = led_rgb
        self.last_seen_monotonic_s: float | None = None
        self.transport = IsoTpEndpoint(
            tx_id=ids.button_pad_transport_device_to_coordinator,
            rx_id=ids.button_pad_transport_coordinator_to_device,
            send_frame=bus.send,
            maximum_payload_length=ids.button_pad_transport_maximum_payload_length,
        )

    def send_button_event(self, button_index: int, pressed: bool) -> CanFrame | None:
        if not 0 <= button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        if not self._operational_with_fresh_lease(self.clock()):
            return None
        frame = encode_button_event(
            ArduinoButtonEventPayload(
                button_index=button_index,
                pressed=pressed,
            ),
            self.ids,
        )
        self._require_bus().send(frame)
        return frame

    def process_pending_led_snapshots(self, *, limit: int = 64) -> list[RgbSnapshotPayload]:
        snapshots: list[RgbSnapshotPayload] = []
        self._process_pending(self.clock(), limit=limit, snapshots=snapshots)
        return snapshots

    def process_pending(self, now: float, *, limit: int = 64) -> int:
        return self._process_pending(now, limit=limit)

    def _process_pending(
        self,
        now: float,
        *,
        limit: int,
        snapshots: list[RgbSnapshotPayload] | None = None,
    ) -> int:
        if limit < 1:
            raise ValueError("simulated device frame limit must be positive")
        bus = self._require_bus()
        processed = 0
        while processed < limit and (frame := bus.receive(timeout_s=0)) is not None:
            processed += 1
            if self._consume_registry_frame(frame, now):
                continue
            self.transport.on_frame(frame)
        self.transport.poll()
        while (payload := self.transport.receive_payload()) is not None:
            if not self._operational_with_fresh_lease(now):
                continue
            try:
                snapshot = decode_rgb_snapshot(payload)
            except ValueError as exc:
                LOGGER.warning("sim neotrellis ignored malformed RGB snapshot: %s", exc)
                continue
            self.led_rgb = snapshot.rgb
            self.last_seen_monotonic_s = now
            if snapshots is not None:
                snapshots.append(snapshot)
        return processed

    def _operational_with_fresh_lease(self, now: float) -> bool:
        return (
            self.state is SimulatedDeviceState.OPERATIONAL
            and self._controller_lease_deadline is not None
            and now < self._controller_lease_deadline
        )



@dataclass
class SimulatedVehicleNode:
    """External simulation node with explicitly synthetic vehicle messages."""

    buses: dict[CanNetwork, CanEndpoint]
    speed_kph: float | None = None
    rpm: int | None = None
    oil_temperature_c: float | None = None
    coolant_temperature_c: float | None = None
    high_beam_enabled: bool = False

    def set_speed(self, speed_kph: float) -> CanFrame:
        frame = encode_simulated_speed(speed_kph)
        self.speed_kph = speed_kph
        self.buses[CanNetwork.FCAN].send(frame)
        return frame

    def emit_speed(self) -> CanFrame | None:
        if self.speed_kph is None:
            return None
        frame = encode_simulated_speed(self.speed_kph)
        self.buses[CanNetwork.FCAN].send(frame)
        return frame

    def silence_speed(self) -> None:
        self.speed_kph = None

    def set_engine_rpm(self, rpm: int) -> CanFrame:
        frame = encode_simulated_engine_rpm(rpm)
        self.rpm = rpm
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def emit_engine_rpm(self) -> CanFrame | None:
        if self.rpm is None:
            return None
        frame = encode_simulated_engine_rpm(self.rpm)
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def silence_engine_rpm(self) -> None:
        self.rpm = None

    def set_oil_temperature(self, temperature_c: float) -> CanFrame:
        frame = encode_simulated_oil_temperature(temperature_c)
        self.oil_temperature_c = decode_simulated_temperature(frame)
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def emit_oil_temperature(self) -> CanFrame | None:
        if self.oil_temperature_c is None:
            return None
        frame = encode_simulated_oil_temperature(self.oil_temperature_c)
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def silence_oil_temperature(self) -> None:
        self.oil_temperature_c = None

    def set_coolant_temperature(self, temperature_c: float) -> CanFrame:
        frame = encode_simulated_coolant_temperature(temperature_c)
        self.coolant_temperature_c = decode_simulated_temperature(frame)
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def emit_coolant_temperature(self) -> CanFrame | None:
        if self.coolant_temperature_c is None:
            return None
        frame = encode_simulated_coolant_temperature(self.coolant_temperature_c)
        self.buses[CanNetwork.PTCAN].send(frame)
        return frame

    def silence_coolant_temperature(self) -> None:
        self.coolant_temperature_c = None

    def drain_pending(self) -> int:
        drained = 0
        for network in CanNetwork:
            bus = self.buses.get(network)
            if bus is None:
                continue
            while (frame := bus.receive(timeout_s=0)) is not None:
                drained += 1
                self._consume_frame(network, frame)
        return drained

    def _consume_frame(self, network: CanNetwork, frame: CanFrame) -> None:
        if (
            network is not CanNetwork.KCAN
            or not frame.is_extended_id
            or frame.arbitration_id != SIMULATION_ONLY_HIGH_BEAM_COMMAND_ID
        ):
            return
        try:
            self.high_beam_enabled = decode_simulated_high_beam_command(frame)
        except ValueError as exc:
            LOGGER.warning(
                "simulated vehicle ignored malformed high-beam command: data=%s error=%s",
                frame.data.hex(),
                exc,
            )


class SimulatedServotronicPeer(SimulatedRegistryPeer):
    """Virtual Servotronic peer with an in-process dimensionless actuator model."""

    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float] = time.monotonic,
        *,
        bus: CanEndpoint | None = None,
        ids: CustomCanIds | None = None,
    ) -> None:
        super().__init__(
            role=DeviceRole.SERVOTRONIC_CONTROLLER,
            bus=bus,
            ids=ids,
            clock=clock,
        )
        self.watchdog_timeout_s = watchdog_timeout_s
        self.last_command: SetSteeringAssistance | None = None
        self.last_command_at: float | None = None

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.last_command = command
        self.last_command_at = self.clock()

    @property
    def watchdog_timed_out(self) -> bool:
        return self.last_command_at is None or (
            self.clock() - self.last_command_at > self.watchdog_timeout_s
        )

    @property
    def effective_assistance(self) -> float:
        if self.watchdog_timed_out or self.last_command is None:
            return 0.0
        return self.last_command.assistance

    @property
    def last_command_reason(self) -> SteeringCommandReason | None:
        return None if self.last_command is None else self.last_command.reason
