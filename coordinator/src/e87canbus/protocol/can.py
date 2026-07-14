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
