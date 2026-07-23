"""Transport-independent operator requests and their dispatch boundary."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypeGuard, assert_never

from e87canbus.application.state import SteeringMode


@dataclass(frozen=True)
class OperatorIntentContext:
    """Server execution context shared by all operator-intent input adapters."""

    observed_at: float | None = None

    def __post_init__(self) -> None:
        if self.observed_at is not None and (
            isinstance(self.observed_at, bool)
            or not isinstance(self.observed_at, (int, float))
            or not math.isfinite(self.observed_at)
            or self.observed_at < 0
        ):
            raise ValueError("observed_at must be a finite non-negative number or None")


DEFAULT_OPERATOR_INTENT_CONTEXT = OperatorIntentContext()


@dataclass(frozen=True)
class SelectSteeringMode:
    """Select an exact normal steering mode without changing its remembered level."""

    mode: SteeringMode

    def __post_init__(self) -> None:
        if not isinstance(self.mode, SteeringMode):
            raise ValueError("mode must be a supported SteeringMode value")


@dataclass(frozen=True)
class ToggleAutomaticAssistance:
    """Toggle whether automatic steering assistance is active."""


@dataclass(frozen=True)
class AdjustManualAssistance:
    """Move the remembered manual-assistance level by a relative number of stages."""

    delta: int

    def __post_init__(self) -> None:
        if type(self.delta) is not int or self.delta not in (-1, 1):
            raise ValueError("manual assistance delta must be -1 or 1")


@dataclass(frozen=True)
class SetManualAssistanceLevel:
    """Select Manual mode at an exact assistance stage."""

    level: int

    def __post_init__(self) -> None:
        if type(self.level) is not int or self.level < 0:
            raise ValueError("manual assistance level must be a non-negative integer")


@dataclass(frozen=True)
class SetMaximumAssistance:
    enabled: bool

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")


@dataclass(frozen=True)
class ToggleMaximumAssistance:
    """Toggle the temporary maximum-assistance override."""


@dataclass(frozen=True)
class StartHighBeamStrobe:
    """Start the configured bounded high-beam strobe action."""


@dataclass(frozen=True)
class ToggleButtonPadDemoBreathe:
    """Toggle the development-only button-pad breathe demonstration."""


OperatorIntent = (
    SelectSteeringMode
    | ToggleAutomaticAssistance
    | AdjustManualAssistance
    | SetManualAssistanceLevel
    | SetMaximumAssistance
    | ToggleMaximumAssistance
    | StartHighBeamStrobe
    | ToggleButtonPadDemoBreathe
)

_OPERATOR_INTENT_TYPES = (
    SelectSteeringMode,
    ToggleAutomaticAssistance,
    AdjustManualAssistance,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    ToggleMaximumAssistance,
    StartHighBeamStrobe,
    ToggleButtonPadDemoBreathe,
)


def is_operator_intent(value: object) -> TypeGuard[OperatorIntent]:
    """Return whether a value belongs to the closed operator-intent vocabulary."""

    return isinstance(value, _OPERATOR_INTENT_TYPES)


def intent_requires_servotronic(intent: OperatorIntent) -> bool:
    """Return whether executing an intent requires usable Servotronic output.

    This exhaustive match makes every new catalogue intent choose its capability
    requirements explicitly instead of leaving that decision to an input adapter.
    """

    match intent:
        case (
            SelectSteeringMode()
            | ToggleAutomaticAssistance()
            | AdjustManualAssistance()
            | SetManualAssistanceLevel()
            | SetMaximumAssistance()
            | ToggleMaximumAssistance()
        ):
            return True
        case StartHighBeamStrobe() | ToggleButtonPadDemoBreathe():
            return False
        case _:
            assert_never(intent)
