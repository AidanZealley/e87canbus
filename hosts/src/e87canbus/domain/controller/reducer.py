"""The event reducer: one observed/timer/failure event to its next state.

``transition`` is the pure reducer for observed vehicle samples, control ticks,
and fallbacks. ``Transition`` is shared with the intent path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.config import SteeringConfig
from e87canbus.domain.controller.steering import steering_command
from e87canbus.domain.events import (
    ApplicationEffect,
    ApplicationEvent,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.domain.steering.curves import SteeringCurveDefinition, clamp_manual_level


@dataclass(frozen=True)
class Transition:
    state: ApplicationState
    effects: tuple[ApplicationEffect, ...] = ()


def transition(
    state: ApplicationState,
    event: ApplicationEvent,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> Transition:
    """Return the complete next state and ordered effects for one event."""

    match event:
        case SpeedObserved(sample):
            next_state = replace(
                state,
                speed_sample=replace(sample, speed_kph=max(0.0, sample.speed_kph)),
                speed_evaluated_at=max(state.speed_evaluated_at, sample.observed_at),
            )
            # Starting the virtual car publishes an explicit 0 km/h sample.  Apply
            # Auto's curve result immediately so the live marker never renders the
            # prior zero-assist fallback while waiting for the next control tick.
            if (
                not isinstance(next_state.steering, MaximumAssistance)
                and next_state.steering.mode is SteeringMode.AUTO
                and sample.speed_kph == 0.0
            ):
                return Transition(
                    next_state,
                    (steering_command(next_state, config, active_definition),),
                )
            return Transition(next_state)
        case EngineRpmObserved(sample):
            return Transition(replace(state, engine_rpm_sample=sample))
        case OilTemperatureObserved(sample):
            return Transition(replace(state, oil_temperature_sample=sample))
        case CoolantTemperatureObserved(sample):
            return Transition(replace(state, coolant_temperature_sample=sample))
        case ControlTimerElapsed(now):
            next_state = replace(
                state,
                speed_evaluated_at=max(state.speed_evaluated_at, now),
                engine_telemetry_evaluated_at=max(
                    state.engine_telemetry_evaluated_at,
                    now,
                ),
            )
            return Transition(
                next_state,
                (steering_command(next_state, config, active_definition),),
            )
        case SteeringFallbackRequested(reason):
            return Transition(
                state,
                (
                    SetSteeringAssistance(
                        0.0,
                        _fallback_command_reason(reason),
                    ),
                ),
            )
        case _:
            assert_never(event)


def normalize_state(state: ApplicationState, config: SteeringConfig) -> ApplicationState:
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    normal = replace(
        normal,
        manual_level=clamp_manual_level(normal.manual_level, config.manual_level_count),
    )
    return replace(
        state,
        steering=(
            MaximumAssistance(previous=normal)
            if isinstance(steering, MaximumAssistance)
            else normal
        ),
    )


def _fallback_command_reason(
    reason: SteeringFallbackReason,
) -> SteeringCommandReason:
    match reason:
        case SteeringFallbackReason.CAN_READER_FAILURE:
            return SteeringCommandReason.CAN_READER_FAILURE
        case SteeringFallbackReason.INBOX_OVERFLOW:
            return SteeringCommandReason.INBOX_OVERFLOW
        case SteeringFallbackReason.SHUTDOWN:
            return SteeringCommandReason.SHUTDOWN
        case _:
            assert_never(reason)
