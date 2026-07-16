"""CAN frame values and project-specific wire codecs."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.generated import (
    BUTTON_EVENT_BUTTON_INDEX_BYTE,
    BUTTON_EVENT_LENGTH,
    BUTTON_EVENT_STATE_BYTE,
    BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_HIGH_BYTE,
    BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_LOW_BYTE,
    BUTTON_PAD_HEARTBEAT_DEVICE_ID_HIGH_BYTE,
    BUTTON_PAD_HEARTBEAT_DEVICE_ID_LOW_BYTE,
    BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_HIGH_BYTE,
    BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_LOW_BYTE,
    BUTTON_PAD_HEARTBEAT_LENGTH,
    BUTTON_PAD_HEARTBEAT_SEQUENCE_BYTE,
    BUTTON_PAD_HEARTBEAT_STATUS_BYTE,
    BUTTON_PAD_HELLO_DEVICE_ID_HIGH_BYTE,
    BUTTON_PAD_HELLO_DEVICE_ID_LOW_BYTE,
    BUTTON_PAD_HELLO_DEVICE_SESSION_ID_HIGH_BYTE,
    BUTTON_PAD_HELLO_DEVICE_SESSION_ID_LOW_BYTE,
    BUTTON_PAD_HELLO_LENGTH,
    BUTTON_PAD_HELLO_PROTOCOL_VERSION_BYTE,
    BUTTON_PAD_HELLO_RESERVED_6_BYTE,
    BUTTON_PAD_HELLO_RESERVED_7_BYTE,
    BUTTON_PAD_HELLO_SEQUENCE_BYTE,
    BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_HIGH_BYTE,
    BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_LOW_BYTE,
    BUTTON_PAD_WELCOME_ACK_DEVICE_ID_HIGH_BYTE,
    BUTTON_PAD_WELCOME_ACK_DEVICE_ID_LOW_BYTE,
    BUTTON_PAD_WELCOME_ACK_DEVICE_SEQUENCE_BYTE,
    BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_HIGH_BYTE,
    BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_LOW_BYTE,
    BUTTON_PAD_WELCOME_ACK_LENGTH,
    BUTTON_PAD_WELCOME_ACK_VERSION_AND_RESPONSE_BYTE,
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    LED_COLOUR_MAX,
    LED_COUNT,
    LED_EVEN_INDEX_SHIFT,
    LED_NIBBLE_MASK,
    LED_ODD_INDEX_SHIFT,
    LED_SNAPSHOT_LENGTH,
)


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    is_extended_id: bool = False


@dataclass(frozen=True)
class RoutedCanFrame:
    """A transport frame paired with the network on which it was observed."""

    network: CanNetwork
    frame: CanFrame


@dataclass(frozen=True)
class ArduinoButtonEventPayload:
    button_index: int
    pressed: bool


@dataclass(frozen=True)
class LedSnapshotPayload:
    colour_codes: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.colour_codes) != LED_COUNT:
            raise ValueError(f"LED snapshot must contain exactly {LED_COUNT} colours")
        if any(
            not isinstance(colour, int) or not 0 <= colour <= LED_COLOUR_MAX
            for colour in self.colour_codes
        ):
            raise ValueError("LED snapshot contains an invalid colour code")


@dataclass(frozen=True)
class DeviceHelloPayload:
    protocol_version: int
    device_id: int
    device_session_id: int
    sequence: int

    def __post_init__(self) -> None:
        _require_uint(self.protocol_version, 8, "protocol_version")
        _require_uint(self.device_id, 16, "device_id")
        _require_uint(self.device_session_id, 16, "device_session_id")
        _require_uint(self.sequence, 8, "sequence")


@dataclass(frozen=True)
class DeviceWelcomeAckPayload:
    controller_protocol_version: int
    response_code: int
    device_id: int
    device_session_id: int
    controller_session_id: int
    device_sequence: int

    def __post_init__(self) -> None:
        _require_uint(self.controller_protocol_version, 4, "controller_protocol_version")
        if self.response_code not in (0, 1):
            raise ValueError("response_code must be accepted (0) or unsupported (1)")
        _require_uint(self.device_id, 16, "device_id")
        _require_uint(self.device_session_id, 16, "device_session_id")
        _require_uint(self.controller_session_id, 16, "controller_session_id")
        _require_uint(self.device_sequence, 8, "device_sequence")


@dataclass(frozen=True)
class DeviceHeartbeatPayload:
    device_id: int
    device_session_id: int
    controller_session_id: int
    sequence: int
    status: int

    def __post_init__(self) -> None:
        _require_uint(self.device_id, 16, "device_id")
        _require_uint(self.device_session_id, 16, "device_session_id")
        _require_uint(self.controller_session_id, 16, "controller_session_id")
        _require_uint(self.sequence, 8, "sequence")
        _require_uint(self.status, 8, "status")


def _require_uint(value: int, bits: int, name: str) -> None:
    if type(value) is not int or not 0 <= value < (1 << bits):
        raise ValueError(f"{name} must fit in an unsigned {bits}-bit value")


def _require_standard_id(arbitration_id: int) -> None:
    if type(arbitration_id) is not int or not 0 <= arbitration_id <= 0x7FF:
        raise ValueError("registry arbitration ID must be an unsigned standard 11-bit ID")


def _registry_frame(frame: CanFrame, arbitration_id: int, length: int) -> bool:
    _require_standard_id(arbitration_id)
    if frame.arbitration_id != arbitration_id:
        return False
    if frame.is_extended_id:
        raise ValueError("registry frames must use standard CAN IDs")
    if len(frame.data) != length:
        raise ValueError(f"registry payload must be exactly {length} bytes")
    return True


def _put_uint16(data: bytearray, value: int, low_byte: int, high_byte: int) -> None:
    data[low_byte] = value & 0xFF
    data[high_byte] = value >> 8


def _get_uint16(data: bytes, low_byte: int, high_byte: int) -> int:
    return data[low_byte] | (data[high_byte] << 8)


def encode_hello(payload: DeviceHelloPayload, arbitration_id: int) -> CanFrame:
    _require_standard_id(arbitration_id)
    data = bytearray(BUTTON_PAD_HELLO_LENGTH)
    data[BUTTON_PAD_HELLO_PROTOCOL_VERSION_BYTE] = payload.protocol_version
    _put_uint16(
        data,
        payload.device_id,
        BUTTON_PAD_HELLO_DEVICE_ID_LOW_BYTE,
        BUTTON_PAD_HELLO_DEVICE_ID_HIGH_BYTE,
    )
    _put_uint16(
        data,
        payload.device_session_id,
        BUTTON_PAD_HELLO_DEVICE_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_HELLO_DEVICE_SESSION_ID_HIGH_BYTE,
    )
    data[BUTTON_PAD_HELLO_SEQUENCE_BYTE] = payload.sequence
    return CanFrame(arbitration_id, bytes(data))


def decode_hello(frame: CanFrame, arbitration_id: int) -> DeviceHelloPayload | None:
    if not _registry_frame(frame, arbitration_id, BUTTON_PAD_HELLO_LENGTH):
        return None
    if (
        frame.data[BUTTON_PAD_HELLO_RESERVED_6_BYTE] != 0
        or frame.data[BUTTON_PAD_HELLO_RESERVED_7_BYTE] != 0
    ):
        raise ValueError("HELLO reserved bytes must be zero")
    return DeviceHelloPayload(
        protocol_version=frame.data[BUTTON_PAD_HELLO_PROTOCOL_VERSION_BYTE],
        device_id=_get_uint16(
            frame.data,
            BUTTON_PAD_HELLO_DEVICE_ID_LOW_BYTE,
            BUTTON_PAD_HELLO_DEVICE_ID_HIGH_BYTE,
        ),
        device_session_id=_get_uint16(
            frame.data,
            BUTTON_PAD_HELLO_DEVICE_SESSION_ID_LOW_BYTE,
            BUTTON_PAD_HELLO_DEVICE_SESSION_ID_HIGH_BYTE,
        ),
        sequence=frame.data[BUTTON_PAD_HELLO_SEQUENCE_BYTE],
    )


def encode_welcome_ack(payload: DeviceWelcomeAckPayload, arbitration_id: int) -> CanFrame:
    _require_standard_id(arbitration_id)
    data = bytearray(BUTTON_PAD_WELCOME_ACK_LENGTH)
    data[BUTTON_PAD_WELCOME_ACK_VERSION_AND_RESPONSE_BYTE] = (
        payload.controller_protocol_version << 4
    ) | payload.response_code
    _put_uint16(
        data,
        payload.device_id,
        BUTTON_PAD_WELCOME_ACK_DEVICE_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_DEVICE_ID_HIGH_BYTE,
    )
    _put_uint16(
        data,
        payload.device_session_id,
        BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_HIGH_BYTE,
    )
    _put_uint16(
        data,
        payload.controller_session_id,
        BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_HIGH_BYTE,
    )
    data[BUTTON_PAD_WELCOME_ACK_DEVICE_SEQUENCE_BYTE] = payload.device_sequence
    return CanFrame(arbitration_id, bytes(data))


def decode_welcome_ack(frame: CanFrame, arbitration_id: int) -> DeviceWelcomeAckPayload | None:
    if not _registry_frame(frame, arbitration_id, BUTTON_PAD_WELCOME_ACK_LENGTH):
        return None
    version_and_response = frame.data[BUTTON_PAD_WELCOME_ACK_VERSION_AND_RESPONSE_BYTE]
    response_code = version_and_response & 0x0F
    if response_code not in (0, 1):
        raise ValueError("WELCOME_ACK response code is reserved")
    return DeviceWelcomeAckPayload(
        controller_protocol_version=version_and_response >> 4,
        response_code=response_code,
        device_id=_get_uint16(
            frame.data,
            BUTTON_PAD_WELCOME_ACK_DEVICE_ID_LOW_BYTE,
            BUTTON_PAD_WELCOME_ACK_DEVICE_ID_HIGH_BYTE,
        ),
        device_session_id=_get_uint16(
            frame.data,
            BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_LOW_BYTE,
            BUTTON_PAD_WELCOME_ACK_DEVICE_SESSION_ID_HIGH_BYTE,
        ),
        controller_session_id=_get_uint16(
            frame.data,
            BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_LOW_BYTE,
            BUTTON_PAD_WELCOME_ACK_CONTROLLER_SESSION_ID_HIGH_BYTE,
        ),
        device_sequence=frame.data[BUTTON_PAD_WELCOME_ACK_DEVICE_SEQUENCE_BYTE],
    )


def encode_heartbeat(payload: DeviceHeartbeatPayload, arbitration_id: int) -> CanFrame:
    _require_standard_id(arbitration_id)
    data = bytearray(BUTTON_PAD_HEARTBEAT_LENGTH)
    _put_uint16(
        data,
        payload.device_id,
        BUTTON_PAD_HEARTBEAT_DEVICE_ID_LOW_BYTE,
        BUTTON_PAD_HEARTBEAT_DEVICE_ID_HIGH_BYTE,
    )
    _put_uint16(
        data,
        payload.device_session_id,
        BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_HIGH_BYTE,
    )
    _put_uint16(
        data,
        payload.controller_session_id,
        BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_LOW_BYTE,
        BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_HIGH_BYTE,
    )
    data[BUTTON_PAD_HEARTBEAT_SEQUENCE_BYTE] = payload.sequence
    data[BUTTON_PAD_HEARTBEAT_STATUS_BYTE] = payload.status
    return CanFrame(arbitration_id, bytes(data))


def decode_heartbeat(frame: CanFrame, arbitration_id: int) -> DeviceHeartbeatPayload | None:
    if not _registry_frame(frame, arbitration_id, BUTTON_PAD_HEARTBEAT_LENGTH):
        return None
    return DeviceHeartbeatPayload(
        device_id=_get_uint16(
            frame.data,
            BUTTON_PAD_HEARTBEAT_DEVICE_ID_LOW_BYTE,
            BUTTON_PAD_HEARTBEAT_DEVICE_ID_HIGH_BYTE,
        ),
        device_session_id=_get_uint16(
            frame.data,
            BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_LOW_BYTE,
            BUTTON_PAD_HEARTBEAT_DEVICE_SESSION_ID_HIGH_BYTE,
        ),
        controller_session_id=_get_uint16(
            frame.data,
            BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_LOW_BYTE,
            BUTTON_PAD_HEARTBEAT_CONTROLLER_SESSION_ID_HIGH_BYTE,
        ),
        sequence=frame.data[BUTTON_PAD_HEARTBEAT_SEQUENCE_BYTE],
        status=frame.data[BUTTON_PAD_HEARTBEAT_STATUS_BYTE],
    )


def encode_button_event(payload: ArduinoButtonEventPayload, ids: CustomCanIds) -> CanFrame:
    state = BUTTON_PRESSED if payload.pressed else BUTTON_RELEASED
    data = bytearray(BUTTON_EVENT_LENGTH)
    data[BUTTON_EVENT_BUTTON_INDEX_BYTE] = payload.button_index
    data[BUTTON_EVENT_STATE_BYTE] = state
    return CanFrame(ids.button_event, bytes(data))


def decode_button_event(frame: CanFrame, ids: CustomCanIds) -> ArduinoButtonEventPayload | None:
    if frame.arbitration_id != ids.button_event:
        return None
    if frame.is_extended_id:
        raise ValueError("button event frames must use a standard CAN ID")
    if len(frame.data) != BUTTON_EVENT_LENGTH:
        raise ValueError(f"button event payload must be exactly {BUTTON_EVENT_LENGTH} bytes")
    state = frame.data[BUTTON_EVENT_STATE_BYTE]
    if state not in (BUTTON_RELEASED, BUTTON_PRESSED):
        raise ValueError("button event state must be released or pressed")
    if frame.data[BUTTON_EVENT_BUTTON_INDEX_BYTE] >= LED_COUNT:
        raise ValueError(f"button event index must be between 0 and {LED_COUNT - 1}")
    return ArduinoButtonEventPayload(
        button_index=frame.data[BUTTON_EVENT_BUTTON_INDEX_BYTE],
        pressed=state == BUTTON_PRESSED,
    )


def encode_led_snapshot(payload: LedSnapshotPayload, ids: CustomCanIds) -> CanFrame:
    data = bytes(
        payload.colour_codes[index] << LED_EVEN_INDEX_SHIFT
        | payload.colour_codes[index + 1] << LED_ODD_INDEX_SHIFT
        for index in range(0, LED_COUNT, 2)
    )
    return CanFrame(ids.led_snapshot, data)


def decode_led_snapshot(frame: CanFrame, ids: CustomCanIds) -> LedSnapshotPayload | None:
    if frame.arbitration_id != ids.led_snapshot:
        return None
    if frame.is_extended_id:
        raise ValueError("LED snapshot frames must use a standard CAN ID")
    if len(frame.data) != LED_SNAPSHOT_LENGTH:
        raise ValueError(f"LED snapshot payload must be exactly {LED_SNAPSHOT_LENGTH} bytes")
    colour_codes = tuple(
        colour
        for packed in frame.data
        for colour in (
            (packed >> LED_EVEN_INDEX_SHIFT) & LED_NIBBLE_MASK,
            (packed >> LED_ODD_INDEX_SHIFT) & LED_NIBBLE_MASK,
        )
    )
    return LedSnapshotPayload(colour_codes)
