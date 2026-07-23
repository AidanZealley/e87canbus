"""The base virtual registry peer shared by the simulated devices."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from enum import StrEnum

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.config import CustomCanIds
from e87canbus.domain.device import DeviceRole
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    DeviceWelcomeAckPayload,
    decode_welcome_ack,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.protocol.generated import CUSTOM_DEVICE_PROTOCOL_VERSION

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
        self.protocol_version = CUSTOM_DEVICE_PROTOCOL_VERSION
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
