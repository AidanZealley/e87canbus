"""CAN frame values and project-specific wire codecs."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.generated import (
    BUTTON_EVENT_BUTTON_INDEX_BYTE,
    BUTTON_EVENT_LENGTH,
    BUTTON_EVENT_STATE_BYTE,
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    LED_UPDATE_BUTTON_INDEX_BYTE,
    LED_UPDATE_COLOUR_BYTE,
    LED_UPDATE_LENGTH,
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
class LedUpdatePayload:
    button_index: int
    colour_code: int


def encode_button_event(payload: ArduinoButtonEventPayload, ids: CustomCanIds) -> CanFrame:
    state = BUTTON_PRESSED if payload.pressed else BUTTON_RELEASED
    data = bytearray(BUTTON_EVENT_LENGTH)
    data[BUTTON_EVENT_BUTTON_INDEX_BYTE] = payload.button_index
    data[BUTTON_EVENT_STATE_BYTE] = state
    return CanFrame(ids.button_event, bytes(data))


def decode_button_event(frame: CanFrame, ids: CustomCanIds) -> ArduinoButtonEventPayload | None:
    if frame.arbitration_id != ids.button_event:
        return None
    if len(frame.data) != BUTTON_EVENT_LENGTH:
        raise ValueError(f"button event payload must be exactly {BUTTON_EVENT_LENGTH} bytes")
    state = frame.data[BUTTON_EVENT_STATE_BYTE]
    if state not in (BUTTON_RELEASED, BUTTON_PRESSED):
        raise ValueError("button event state must be released or pressed")
    return ArduinoButtonEventPayload(
        button_index=frame.data[BUTTON_EVENT_BUTTON_INDEX_BYTE],
        pressed=state == BUTTON_PRESSED,
    )


def encode_led_update(payload: LedUpdatePayload, ids: CustomCanIds) -> CanFrame:
    data = bytearray(LED_UPDATE_LENGTH)
    data[LED_UPDATE_BUTTON_INDEX_BYTE] = payload.button_index
    data[LED_UPDATE_COLOUR_BYTE] = payload.colour_code
    return CanFrame(ids.led_update, bytes(data))


def decode_led_update(frame: CanFrame, ids: CustomCanIds) -> LedUpdatePayload | None:
    if frame.arbitration_id != ids.led_update:
        return None
    if len(frame.data) != LED_UPDATE_LENGTH:
        raise ValueError(f"LED update payload must be exactly {LED_UPDATE_LENGTH} bytes")
    return LedUpdatePayload(
        button_index=frame.data[LED_UPDATE_BUTTON_INDEX_BYTE],
        colour_code=frame.data[LED_UPDATE_COLOUR_BYTE],
    )
