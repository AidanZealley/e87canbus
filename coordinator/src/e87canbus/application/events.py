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


class SteeringCommandReason(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    MAXIMUM = "maximum"
    SPEED_NEVER_OBSERVED = "speed_never_observed"
    SPEED_STALE = "speed_stale"
    CAN_READER_FAILURE = "can_reader_failure"
    INBOX_OVERFLOW = "inbox_overflow"
    SHUTDOWN = "shutdown"


class SteeringFallbackReason(StrEnum):
    CAN_READER_FAILURE = "can_reader_failure"
    INBOX_OVERFLOW = "inbox_overflow"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class SteeringFallbackRequested:
    reason: SteeringFallbackReason


ApplicationEvent = (
    ButtonPressed | SpeedObserved | ControlTimerElapsed | SteeringFallbackRequested
)


@dataclass(frozen=True)
class SetButtonLed:
    button_index: int
    colour: LedColour


@dataclass(frozen=True)
class SetSteeringAssistance:
    """Dimensionless command for a capability supplied by composition."""

    assistance: float
    reason: SteeringCommandReason

    def __post_init__(self) -> None:
        if not 0.0 <= self.assistance <= 1.0:
            raise ValueError("steering assistance must be between zero and one")


ApplicationEffect = SetButtonLed | SetSteeringAssistance
