"""Internal events routed by the Pi application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.config import CanNetwork


class SteeringMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


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
    source_network: CanNetwork
