"""Immutable domain state values."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from e87canbus.config import CanNetwork


class SteeringMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class ButtonFeedbackColour(StrEnum):
    RED = "red"
    AMBER = "amber"
    WHITE = "white"


@dataclass(frozen=True)
class NormalSteering:
    mode: SteeringMode = SteeringMode.AUTO
    manual_level: int = 0


@dataclass(frozen=True)
class MaximumAssistance:
    previous: NormalSteering


SteeringState = NormalSteering | MaximumAssistance


@dataclass(frozen=True)
class SpeedSample:
    speed_kph: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class EngineRpmSample:
    rpm: int
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class OilTemperatureSample:
    temperature_c: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class CoolantTemperatureSample:
    temperature_c: float
    observed_at: float
    source_network: CanNetwork


@dataclass(frozen=True)
class ApplicationState:
    steering: SteeringState = field(default_factory=NormalSteering)
    speed_sample: SpeedSample | None = None
    speed_evaluated_at: float = 0.0
    engine_rpm_sample: EngineRpmSample | None = None
    oil_temperature_sample: OilTemperatureSample | None = None
    coolant_temperature_sample: CoolantTemperatureSample | None = None
    engine_telemetry_evaluated_at: float = 0.0
    high_beam_enabled: bool = False
    high_beam_strobe_cycles_remaining: int = 0
    high_beam_next_transition_at: float | None = None
    button_feedback_deadlines: tuple[float | None, ...] = (None,) * 16
    button_feedback_colours: tuple[ButtonFeedbackColour | None, ...] = (None,) * 16
    button_pad_demo_breathe_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.button_pad_demo_breathe_enabled) is not bool:
            raise ValueError("button pad demo breathe flag must be a boolean")
        if len(self.button_feedback_deadlines) != 16:
            raise ValueError("button feedback deadlines must contain exactly 16 entries")
        if len(self.button_feedback_colours) != 16:
            raise ValueError("button feedback colours must contain exactly 16 entries")
        for deadline in self.button_feedback_deadlines:
            if deadline is not None and not math.isfinite(deadline):
                raise ValueError("button feedback deadlines must be finite")
        if any(
            colour is not None and not isinstance(colour, ButtonFeedbackColour)
            for colour in self.button_feedback_colours
        ):
            raise ValueError("button feedback colours must be ButtonFeedbackColour values")
