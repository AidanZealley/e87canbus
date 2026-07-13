"""Closed application event and effect values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.state import SpeedSample


class LedColour(StrEnum):
    OFF = "off"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    AMBER = "amber"
    WHITE = "white"


@dataclass(frozen=True)
class ButtonPressed:
    button_index: int


@dataclass(frozen=True)
class SpeedObserved:
    sample: SpeedSample


@dataclass(frozen=True)
class ControlTimerElapsed:
    now: float


ApplicationEvent = ButtonPressed | SpeedObserved | ControlTimerElapsed


@dataclass(frozen=True)
class SetButtonLed:
    button_index: int
    colour: LedColour


ApplicationEffect = SetButtonLed
