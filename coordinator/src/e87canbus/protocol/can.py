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


BUTTON_PAD_PROGRAM_VERSION = 2
BUTTON_PAD_REPLACE_ALL = 1
BUTTON_PAD_SET_TRACK = 2
BUTTON_PAD_COMMIT = 0x80
BUTTON_PAD_TRACK_SOLID = 1
BUTTON_PAD_TRACK_BLINK = 2
BUTTON_PAD_TRACK_BREATHE = 3
BUTTON_PAD_COMMAND_LENGTH = 16
BUTTON_PAD_TRANSFER_MAX_LENGTH = 64


@dataclass(frozen=True)
class ButtonPadTrackPayload:
    kind: int
    rgb: tuple[int, int, int]
    parameter_a: int = 0
    parameter_b: int = 0
    repeat: int = 0
    final_rgb: tuple[int, int, int] = (0, 0, 0)

    def __post_init__(self) -> None:
        if self.kind not in (
            BUTTON_PAD_TRACK_SOLID,
            BUTTON_PAD_TRACK_BLINK,
            BUTTON_PAD_TRACK_BREATHE,
        ):
            raise ValueError("unsupported button-pad track kind")
        for name, rgb in (("track", self.rgb), ("final", self.final_rgb)):
            if len(rgb) != 3 or any(
                type(value) is not int or not 0 <= value <= 255 for value in rgb
            ):
                raise ValueError(f"button-pad {name} colour must contain RGB bytes")
        _require_uint(self.parameter_a, 16, "button-pad track parameter A")
        _require_uint(self.parameter_b, 16, "button-pad track parameter B")
        _require_uint(self.repeat, 8, "button-pad track repeat")
        if self.kind == BUTTON_PAD_TRACK_SOLID and (
            self.parameter_a or self.parameter_b or self.repeat
        ):
            raise ValueError("solid button-pad tracks cannot have timing or repetition")
        if self.kind == BUTTON_PAD_TRACK_BLINK and not (
            1 <= self.parameter_a <= 10_000 and 1 <= self.parameter_b <= 10_000
        ):
            raise ValueError("blink tracks require bounded positive on/off durations")
        if self.kind == BUTTON_PAD_TRACK_BREATHE:
            minimum = self.parameter_b & 0xFF
            maximum = self.parameter_b >> 8
            if not 250 <= self.parameter_a <= 10_000 or minimum > maximum:
                raise ValueError("breathe tracks require a bounded period and brightness")


@dataclass(frozen=True)
class ButtonPadTrackCommandPayload:
    replace_all: bool
    target_mask: int
    track: ButtonPadTrackPayload
    commit: bool = False

    def __post_init__(self) -> None:
        if type(self.target_mask) is not int or not 0 < self.target_mask < (1 << 16):
            raise ValueError("button-pad track target mask must select one or more LEDs")


ButtonPadProgramPayload = ButtonPadTrackCommandPayload


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
    if frame.data[BUTTON_EVENT_BUTTON_INDEX_BYTE] >= RGB_SNAPSHOT_LED_COUNT:
        raise ValueError(f"button event index must be between 0 and {RGB_SNAPSHOT_LED_COUNT - 1}")
    return ArduinoButtonEventPayload(
        button_index=frame.data[BUTTON_EVENT_BUTTON_INDEX_BYTE],
        pressed=state == BUTTON_PRESSED,
    )


RGB_SNAPSHOT_LED_COUNT = 16


def encode_button_pad_program(payload: ButtonPadProgramPayload) -> bytes:
    """Encode one resolved-track command, bounded to the 64-byte transport."""
    track = payload.track
    return (
        bytes(
            (
                BUTTON_PAD_PROGRAM_VERSION,
                (BUTTON_PAD_REPLACE_ALL if payload.replace_all else BUTTON_PAD_SET_TRACK)
                | (BUTTON_PAD_COMMIT if payload.commit else 0),
            )
        )
        + payload.target_mask.to_bytes(2, "little")
        + bytes((track.kind, *track.rgb))
        + track.parameter_a.to_bytes(2, "little")
        + track.parameter_b.to_bytes(2, "little")
        + bytes((track.repeat, *track.final_rgb))
    )


def decode_button_pad_program(payload: bytes) -> ButtonPadProgramPayload:
    if len(payload) < 2:
        raise ValueError("button-pad program must contain a version and opcode")
    if payload[0] != BUTTON_PAD_PROGRAM_VERSION:
        raise ValueError("unsupported button-pad program version")
    if len(payload) != BUTTON_PAD_COMMAND_LENGTH:
        raise ValueError("button-pad track command must contain exactly 16 bytes")
    opcode = payload[1] & ~BUTTON_PAD_COMMIT
    if opcode not in (BUTTON_PAD_REPLACE_ALL, BUTTON_PAD_SET_TRACK):
        raise ValueError("unsupported button-pad program opcode")
    return ButtonPadTrackCommandPayload(
        replace_all=opcode == BUTTON_PAD_REPLACE_ALL,
        target_mask=int.from_bytes(payload[2:4], "little"),
        track=ButtonPadTrackPayload(
            kind=payload[4],
            rgb=tuple(payload[5:8]),  # type: ignore[arg-type]
            parameter_a=int.from_bytes(payload[8:10], "little"),
            parameter_b=int.from_bytes(payload[10:12], "little"),
            repeat=payload[12],
            final_rgb=tuple(payload[13:16]),  # type: ignore[arg-type]
        ),
        commit=bool(payload[1] & BUTTON_PAD_COMMIT),
    )


def decode_button_pad_commands(payload: bytes) -> tuple[ButtonPadProgramPayload, ...]:
    """Split one ISO-TP transfer into its packed 16-byte track commands."""
    if (
        len(payload) == 0
        or len(payload) % BUTTON_PAD_COMMAND_LENGTH != 0
        or len(payload) > BUTTON_PAD_TRANSFER_MAX_LENGTH
    ):
        raise ValueError("button-pad transfer must pack one to four 16-byte commands")
    return tuple(
        decode_button_pad_program(payload[offset : offset + BUTTON_PAD_COMMAND_LENGTH])
        for offset in range(0, len(payload), BUTTON_PAD_COMMAND_LENGTH)
    )
