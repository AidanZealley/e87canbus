"""Transport-independent operator requests and their dispatch boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeGuard

from e87canbus.domain.state import SteeringMode


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


OperatorIntent = (
    SelectSteeringMode
    | ToggleAutomaticAssistance
    | AdjustManualAssistance
    | SetManualAssistanceLevel
    | SetMaximumAssistance
    | ToggleMaximumAssistance
)

_OPERATOR_INTENT_TYPES = (
    SelectSteeringMode,
    ToggleAutomaticAssistance,
    AdjustManualAssistance,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    ToggleMaximumAssistance,
)


def is_operator_intent(value: object) -> TypeGuard[OperatorIntent]:
    """Return whether a value belongs to the closed operator-intent vocabulary."""

    return isinstance(value, _OPERATOR_INTENT_TYPES)
