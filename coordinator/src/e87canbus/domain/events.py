"""Closed application event and effect values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.domain.buttons.pad import ButtonPadProgram
from e87canbus.domain.state import (
    BUTTON_FEEDBACK_REJECTED,
    ButtonFeedback,
    ButtonVisual,
    CoolantTemperatureSample,
    EngineRpmSample,
    OilTemperatureSample,
    SpeedSample,
)
from e87canbus.domain.steering.curves import SteeringCurveDefinition

BUTTON_LED_COUNT = 16
# Press feedback is rendered and self-terminated on the device. The deadline only
# clears the coordinator's canonical state; no cleanup program needs to be transmitted.
BUTTON_FEEDBACK_BLINK_ON_MS = 100
BUTTON_FEEDBACK_BLINK_OFF_MS = 100
BUTTON_FEEDBACK_CYCLE_MS = BUTTON_FEEDBACK_BLINK_ON_MS + BUTTON_FEEDBACK_BLINK_OFF_MS


def button_feedback_duration_s(pulses: int) -> float:
    """How long the pad spends rendering ``pulses`` on/off cycles."""

    return (BUTTON_FEEDBACK_CYCLE_MS * pulses) / 1000


@dataclass(frozen=True)
class ButtonLedState:
    """What every button is reporting, one entry per button in button order.

    This is the semantic half of the pad's appearance: the pixels follow from it and
    the slot's authored colour and animation, which are fixed for the lifetime of a
    profile. Holding states rather than rendered colours means "did anything on the
    pad change" is a comparison of this value, into which animation phase cannot
    enter, and means an authored breathe needs no wider type here.
    """

    visuals: tuple[ButtonVisual, ...]

    def __post_init__(self) -> None:
        # Membership needs no check: every entry is an enum member by construction.
        if len(self.visuals) != BUTTON_LED_COUNT:
            raise ValueError(
                f"button LED state must contain exactly {BUTTON_LED_COUNT} visual states"
            )


@dataclass(frozen=True)
class ButtonPressed:
    button_index: int
    observed_at: float = 0.0

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button press index must identify a button LED")
        if not math.isfinite(self.observed_at):
            raise ValueError("button observation time must be finite")


@dataclass(frozen=True)
class ButtonCommandFailed:
    button_index: int
    occurred_at: float
    feedback: ButtonFeedback = BUTTON_FEEDBACK_REJECTED

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button failure index must identify a button LED")
        if not math.isfinite(self.occurred_at):
            raise ValueError("button failure time must be finite")
        if not isinstance(self.feedback, ButtonFeedback):
            raise ValueError("button failure feedback must be a ButtonFeedback")


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
    ButtonCommandFailed
    | ButtonFeedbackDeadlineReached
    | SpeedObserved
    | EngineRpmObserved
    | OilTemperatureObserved
    | CoolantTemperatureObserved
    | ControlTimerElapsed
    | HighBeamStrobeDeadlineReached
    | SteeringFallbackRequested
)


@dataclass(frozen=True)
class SetButtonPadProgram:
    program: ButtonPadProgram


@dataclass(frozen=True)
class TriggerButtonPadBlink:
    """The low-latency single-frame feedback blink, carrying its own colour.

    Steady appearance — animated or not — belongs to the button-pad program; this
    frame exists only so a press is acknowledged without waiting on ISO-TP.
    """

    button_index: int
    feedback: ButtonFeedback = BUTTON_FEEDBACK_REJECTED

    def __post_init__(self) -> None:
        if type(self.button_index) is not int or not 0 <= self.button_index < BUTTON_LED_COUNT:
            raise ValueError("button blink index must identify a button LED")
        if not isinstance(self.feedback, ButtonFeedback):
            raise ValueError("button blink feedback must be a ButtonFeedback")


@dataclass(frozen=True)
class SetSteeringAssistance:
    """Dimensionless command for a capability supplied by composition."""

    assistance: float
    reason: SteeringCommandReason

    def __post_init__(self) -> None:
        if not 0.0 <= self.assistance <= 1.0:
            raise ValueError("steering assistance must be between zero and one")


@dataclass(frozen=True)
class ConfigureServotronicCurve:
    definition: SteeringCurveDefinition
    activation_revision: int


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
    | SetSteeringAssistance
    | ConfigureServotronicCurve
    | SetHighBeam
)
