"""Internal events routed by the Pi application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SteeringMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class MflButton(StrEnum):
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    NEXT = "next"
    PREVIOUS = "previous"
    PHONE_PICKUP = "phone_pickup"
    PHONE_HANGUP = "phone_hangup"
    MODE = "mode"


class ButtonState(StrEnum):
    PRESSED = "pressed"
    RELEASED = "released"


class LedColour(StrEnum):
    OFF = "off"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    AMBER = "amber"
    WHITE = "white"


class DscCommand(StrEnum):
    OFF_REQUEST = "off_request"


@dataclass(frozen=True)
class MflButtonEvent:
    button: MflButton
    state: ButtonState


@dataclass(frozen=True)
class NeoTrellisButtonEvent:
    button_index: int
    state: ButtonState


@dataclass(frozen=True)
class ButtonLedCommand:
    button_index: int
    colour: LedColour


@dataclass(frozen=True)
class SpeedUpdateEvent:
    speed_kph: float
    source_bus: str


@dataclass(frozen=True)
class DscCommandRequest:
    command: DscCommand


@dataclass(frozen=True)
class HighBeamStrobeRequest:
    cycles: int | None = None


@dataclass(frozen=True)
class SteeringModeChange:
    mode: SteeringMode


@dataclass(frozen=True)
class ManualAssistanceLevelChange:
    delta: int
