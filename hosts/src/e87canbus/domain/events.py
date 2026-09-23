"""Closed application event and effect values."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.domain.state import (
    CoolantTemperatureSample,
    EngineRpmSample,
    OilTemperatureSample,
    SpeedSample,
)
from e87canbus.domain.steering.curves import SteeringCurveDefinition

BUTTON_LED_COUNT = 16


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
    SpeedObserved
    | EngineRpmObserved
    | OilTemperatureObserved
    | CoolantTemperatureObserved
    | ControlTimerElapsed
    | SteeringFallbackRequested
)


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


ApplicationEffect = SetSteeringAssistance | ConfigureServotronicCurve
