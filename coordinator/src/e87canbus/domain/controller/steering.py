"""Steering-assistance command math derived from application state.

Pure functions that turn the current steering state and speed sample into the
``SetSteeringAssistance`` command the actuator should hold, including the
speed-freshness rules that gate Auto output.
"""

from __future__ import annotations

from e87canbus.config import SteeringConfig
from e87canbus.domain.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.domain.steering import (
    SteeringCurveDefinition,
    interpolate_steering_curve_definition,
)


def steering_command(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM)
    if steering.mode is SteeringMode.MANUAL:
        denominator = max(config.manual_level_count - 1, 1)
        return SetSteeringAssistance(
            steering.manual_level / denominator,
            SteeringCommandReason.MANUAL,
        )
    sample = state.speed_sample
    if sample is None:
        return SetSteeringAssistance(
            0.0,
            SteeringCommandReason.SPEED_NEVER_OBSERVED,
        )
    if not speed_is_valid(state, config):
        return SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_STALE)

    return SetSteeringAssistance(
        interpolate_steering_curve_definition(
            sample.speed_kph,
            active_definition,
        ),
        SteeringCommandReason.AUTO,
    )


def steering_command_for_active_curve(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance | None:
    """Recalculate only when activation can immediately affect Auto output."""

    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    if normal.mode is not SteeringMode.AUTO or isinstance(steering, MaximumAssistance):
        return None
    if not speed_is_valid(state, config):
        return None
    return steering_command(state, config, active_definition)


def steering_command_for_current_state(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance:
    """Build the complete retained command for Servotronic activation sync."""

    return steering_command(state, config, active_definition)


def speed_is_valid(state: ApplicationState, config: SteeringConfig) -> bool:
    sample = state.speed_sample
    return (
        sample is not None
        and state.speed_evaluated_at - sample.observed_at <= config.speed_timeout_s
    )
