"""Pure transitions for vehicle observations and telemetry freshness."""

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.config import SteeringConfig
from e87canbus.domain.events import (
    ApplicationEvent,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SpeedObserved,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance
from e87canbus.domain.steering.curves import clamp_manual_level


@dataclass(frozen=True)
class Transition:
    state: ApplicationState


def transition(state: ApplicationState, event: ApplicationEvent) -> Transition:
    match event:
        case SpeedObserved(sample):
            return Transition(
                replace(
                    state,
                    speed_sample=replace(sample, speed_kph=max(0.0, sample.speed_kph)),
                    speed_evaluated_at=max(state.speed_evaluated_at, sample.observed_at),
                )
            )
        case EngineRpmObserved(sample):
            return Transition(replace(state, engine_rpm_sample=sample))
        case OilTemperatureObserved(sample):
            return Transition(replace(state, oil_temperature_sample=sample))
        case CoolantTemperatureObserved(sample):
            return Transition(replace(state, coolant_temperature_sample=sample))
        case ControlTimerElapsed(now):
            return Transition(
                replace(
                    state,
                    speed_evaluated_at=max(state.speed_evaluated_at, now),
                    engine_telemetry_evaluated_at=max(state.engine_telemetry_evaluated_at, now),
                )
            )
        case _:
            assert_never(event)


def normalize_state(state: ApplicationState, config: SteeringConfig) -> ApplicationState:
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    normal = replace(
        normal, manual_level=clamp_manual_level(normal.manual_level, config.manual_level_count)
    )
    return replace(
        state,
        steering=MaximumAssistance(previous=normal)
        if isinstance(steering, MaximumAssistance)
        else normal,
    )
