"""Closed application event and effect values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.state import (
    CoolantTemperatureSample,
    EngineRpmSample,
    OilTemperatureSample,
    SpeedSample,
    SteeringMode,
)


class LedColour(StrEnum):
    OFF = "off"
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    AMBER = "amber"
    WHITE = "white"


BUTTON_LED_COUNT = 16


@dataclass(frozen=True)
class ButtonLedState:
    colours: tuple[LedColour, ...]

    def __post_init__(self) -> None:
        if len(self.colours) != BUTTON_LED_COUNT:
            raise ValueError(f"button LED state must contain exactly {BUTTON_LED_COUNT} colours")
        if any(not isinstance(colour, LedColour) for colour in self.colours):
            raise ValueError("button LED state must contain only known LED colours")


OFF_BUTTON_LEDS = ButtonLedState((LedColour.OFF,) * BUTTON_LED_COUNT)


@dataclass(frozen=True)
class ButtonPressed:
    button_index: int
    observed_at: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.observed_at):
            raise ValueError("button observation time must be finite")


@dataclass(frozen=True)
class SpeedObserved:
    sample: SpeedSample


@dataclass(frozen=True)
class EngineRpmObserved:
    sample: EngineRpmSample


@dataclass(frozen=True)
class OilTemperatureObserved:
    sample: OilTemperatureSample


@dataclass(frozen=True)
class CoolantTemperatureObserved:
    sample: CoolantTemperatureSample


@dataclass(frozen=True)
class ControlTimerElapsed:
    now: float


@dataclass(frozen=True)
class HighBeamStrobeDeadlineReached:
    """A separately scheduled high-beam strobe phase deadline."""

    now: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.now):
            raise ValueError("high-beam strobe deadline must be finite")


@dataclass(frozen=True)
class MaximumAssistanceSet:
    enabled: bool


@dataclass(frozen=True)
class SteeringModeSet:
    mode: SteeringMode
    manual_level: int | None = None


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
    ButtonPressed
    | SpeedObserved
    | EngineRpmObserved
    | OilTemperatureObserved
    | CoolantTemperatureObserved
    | ControlTimerElapsed
    | HighBeamStrobeDeadlineReached
    | MaximumAssistanceSet
    | SteeringModeSet
    | SteeringFallbackRequested
)


@dataclass(frozen=True)
class SetButtonLeds:
    colours: ButtonLedState


@dataclass(frozen=True)
class SetSteeringAssistance:
    """Dimensionless command for a capability supplied by composition."""

    assistance: float
    reason: SteeringCommandReason

    def __post_init__(self) -> None:
        if not 0.0 <= self.assistance <= 1.0:
            raise ValueError("steering assistance must be between zero and one")


@dataclass(frozen=True)
class SetHighBeam:
    """Protocol-independent high-beam capability request."""

    enabled: bool

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("high-beam enabled must be a boolean")


ApplicationEffect = SetButtonLeds | SetSteeringAssistance | SetHighBeam
