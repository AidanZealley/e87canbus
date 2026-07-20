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
from e87canbus.button_pad import ButtonPadProgram

BUTTON_LED_COUNT = 16
# Press feedback is rendered and self-terminated on the device. The deadline only
# clears the coordinator's canonical state; no cleanup program needs to be transmitted.
BUTTON_FEEDBACK_BLINK_ON_MS = 100
BUTTON_FEEDBACK_BLINK_OFF_MS = 100
BUTTON_FEEDBACK_BLINK_REPEAT = 2
BUTTON_FEEDBACK_DURATION_S = (
    (BUTTON_FEEDBACK_BLINK_ON_MS + BUTTON_FEEDBACK_BLINK_OFF_MS) * BUTTON_FEEDBACK_BLINK_REPEAT
) / 1000
Rgb = tuple[int, int, int]
RGB_OFF: Rgb = (0, 0, 0)
RGB_RED: Rgb = (255, 0, 0)
RGB_BLUE: Rgb = (0, 0, 255)
RGB_AMBER: Rgb = (255, 191, 0)
RGB_WHITE: Rgb = (255, 255, 255)


class ButtonFeedbackColour(StrEnum):
    RED = "red"
    AMBER = "amber"
    WHITE = "white"


@dataclass(frozen=True)
class ButtonLedState:
    rgb: tuple[Rgb, ...]

    def __post_init__(self) -> None:
        if len(self.rgb) != BUTTON_LED_COUNT:
            raise ValueError(f"button LED state must contain exactly {BUTTON_LED_COUNT} RGB values")
        if any(
            len(value) != 3
            or any(type(channel) is not int or not 0 <= channel <= 0xFF for channel in value)
            for value in self.rgb
        ):
            raise ValueError("button LED state must contain only RGB bytes")


OFF_BUTTON_LEDS = ButtonLedState((RGB_OFF,) * BUTTON_LED_COUNT)


@dataclass(frozen=True)
class ButtonPressed:
    button_index: int
    observed_at: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.observed_at):
            raise ValueError("button observation time must be finite")


@dataclass(frozen=True)
class ButtonCommandFailed:
    button_index: int
    occurred_at: float
    blink_colour: ButtonFeedbackColour = ButtonFeedbackColour.RED

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button failure index must identify a button LED")
        if not math.isfinite(self.occurred_at):
            raise ValueError("button failure time must be finite")
        if not isinstance(self.blink_colour, ButtonFeedbackColour):
            raise ValueError("button failure colour must be a ButtonFeedbackColour")


@dataclass(frozen=True)
class ButtonFeedbackDeadlineReached:
    now: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.now):
            raise ValueError("button feedback deadline must be finite")


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
    | ButtonCommandFailed
    | ButtonFeedbackDeadlineReached
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
class SetButtonPadProgram:
    program: ButtonPadProgram


@dataclass(frozen=True)
class TriggerButtonPadBlink:
    button_index: int
    colour: ButtonFeedbackColour = ButtonFeedbackColour.RED

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button blink index must identify a button LED")
        if not isinstance(self.colour, ButtonFeedbackColour):
            raise ValueError("button blink colour must be a ButtonFeedbackColour")


@dataclass(frozen=True)
class SetButtonPadBreathe:
    button_index: int
    enabled: bool

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button breathe index must identify a button LED")
        if type(self.enabled) is not bool:
            raise ValueError("button breathe enabled must be a boolean")


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


ApplicationEffect = (
    SetButtonPadProgram
    | TriggerButtonPadBlink
    | SetButtonPadBreathe
    | SetSteeringAssistance
    | SetHighBeam
)
