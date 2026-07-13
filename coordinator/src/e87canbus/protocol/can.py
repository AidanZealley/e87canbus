"""CAN I/O boundaries and project-specific custom frame helpers."""

from dataclasses import dataclass
from typing import Protocol

from e87canbus.application.events import ButtonLedCommand, LedColour
from e87canbus.config import CanNetwork, CustomCanIds

BUTTON_RELEASED = 0x00
BUTTON_PRESSED = 0x01

LED_OFF = 0x00
LED_RED = 0x01
LED_GREEN = 0x02
LED_BLUE = 0x03
LED_AMBER = 0x04
LED_WHITE = 0x05

LED_COLOUR_CODES = {
    LedColour.OFF: LED_OFF,
    LedColour.RED: LED_RED,
    LedColour.GREEN: LED_GREEN,
    LedColour.BLUE: LED_BLUE,
    LedColour.AMBER: LED_AMBER,
    LedColour.WHITE: LED_WHITE,
}


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


class CanBus(Protocol):
    def send(self, frame: CanFrame) -> None:
        """Send one CAN frame."""

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        """Receive one CAN frame, or None on timeout."""


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
    return CanFrame(ids.button_event, bytes([payload.button_index, state]))


def decode_button_event(frame: CanFrame, ids: CustomCanIds) -> ArduinoButtonEventPayload | None:
    if frame.arbitration_id != ids.button_event:
        return None
    if len(frame.data) != 2:
        raise ValueError("button event payload must be exactly 2 bytes")
    if frame.data[1] not in (BUTTON_RELEASED, BUTTON_PRESSED):
        raise ValueError("button event state must be released or pressed")
    return ArduinoButtonEventPayload(
        button_index=frame.data[0],
        pressed=frame.data[1] == BUTTON_PRESSED,
    )


def encode_led_update(payload: LedUpdatePayload, ids: CustomCanIds) -> CanFrame:
    return CanFrame(ids.led_update, bytes([payload.button_index, payload.colour_code]))


def encode_button_led_command(command: ButtonLedCommand, ids: CustomCanIds) -> CanFrame:
    return encode_led_update(
        LedUpdatePayload(
            button_index=command.button_index,
            colour_code=LED_COLOUR_CODES[command.colour],
        ),
        ids,
    )


def decode_led_update(frame: CanFrame, ids: CustomCanIds) -> LedUpdatePayload | None:
    if frame.arbitration_id != ids.led_update:
        return None
    if len(frame.data) != 2:
        raise ValueError("LED update payload must be exactly 2 bytes")
    return LedUpdatePayload(button_index=frame.data[0], colour_code=frame.data[1])


class SocketCanBus:
    """Future python-can adapter boundary."""

    def __init__(self, interface: str) -> None:
        self.interface = interface
        raise NotImplementedError("SocketCAN integration is out of scope for the initial scaffold")
