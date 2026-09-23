"""Transport-independent vehicle observations and button inputs."""

import math
from dataclasses import dataclass

from e87canbus.domain.state import (
    CoolantTemperatureSample,
    EngineRpmSample,
    OilTemperatureSample,
    SpeedSample,
)

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


ApplicationEvent = (
    SpeedObserved
    | EngineRpmObserved
    | OilTemperatureObserved
    | CoolantTemperatureObserved
    | ControlTimerElapsed
)
