"""Immutable domain state values."""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.application.events import SteeringMode
from e87canbus.config import CanNetwork


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
class ApplicationState:
    steering: SteeringState = field(default_factory=NormalSteering)
    speed_sample: SpeedSample | None = None
    speed_evaluated_at: float = 0.0
