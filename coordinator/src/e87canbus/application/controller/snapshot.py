"""The immutable application snapshot and the startup output projection.

``snapshot`` composes the complete read-only view published to adapters; engine
telemetry freshness and the steering projection are derived here. ``initial_effects``
returns the outputs a fresh kernel must synchronise on startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.controller.button_leds import button_led_effect, button_pad_program
from e87canbus.application.controller.steering import speed_is_valid, steering_command
from e87canbus.application.events import ApplicationEffect
from e87canbus.application.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.button_pad import ButtonPadProgram
from e87canbus.config import EngineTelemetryConfig, HighBeamStrobeConfig, SteeringConfig
from e87canbus.features.steering import (
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
)


class EngineTelemetryStatus(StrEnum):
    VALID = "valid"
    NEVER_OBSERVED = "never_observed"
    STALE = "stale"


@dataclass(frozen=True)
class EngineTelemetryValue:
    value: int | float | None
    status: EngineTelemetryStatus


@dataclass(frozen=True)
class EngineTelemetrySnapshot:
    rpm: EngineTelemetryValue
    oil_temperature_c: EngineTelemetryValue
    coolant_temperature_c: EngineTelemetryValue


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    manual_assistance_level_count: int
    maximum_assistance_active: bool
    speed_valid: bool
    engine: EngineTelemetrySnapshot
    active_steering_curve: ActiveSteeringCurve
    steering_curve_activation_status: SteeringCurveActivationStatus
    curve_activation_available: bool
    button_pad_program: ButtonPadProgram
    high_beam_enabled: bool
    high_beam_strobe_active: bool
    high_beam_strobe_cycles_remaining: int
    high_beam_next_transition_at: float | None


def snapshot(
    state: ApplicationState,
    config: SteeringConfig,
    engine_config: EngineTelemetryConfig,
    active_curve: ActiveSteeringCurve,
    activation_status: SteeringCurveActivationStatus,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
    curve_activation_available: bool = False,
) -> ApplicationSnapshot:
    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
        manual_assistance_level_count=config.manual_level_count,
        maximum_assistance_active=maximum_active,
        speed_valid=speed_is_valid(state, config),
        engine=EngineTelemetrySnapshot(
            rpm=_engine_value(
                None if state.engine_rpm_sample is None else state.engine_rpm_sample.rpm,
                None if state.engine_rpm_sample is None else state.engine_rpm_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
            oil_temperature_c=_engine_value(
                None
                if state.oil_temperature_sample is None
                else state.oil_temperature_sample.temperature_c,
                None
                if state.oil_temperature_sample is None
                else state.oil_temperature_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
            coolant_temperature_c=_engine_value(
                None
                if state.coolant_temperature_sample is None
                else state.coolant_temperature_sample.temperature_c,
                None
                if state.coolant_temperature_sample is None
                else state.coolant_temperature_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
        ),
        active_steering_curve=active_curve,
        steering_curve_activation_status=activation_status,
        curve_activation_available=curve_activation_available,
        button_pad_program=button_pad_program(state, servotronic_usable, high_beam_button_index),
        high_beam_enabled=state.high_beam_enabled,
        high_beam_strobe_active=state.high_beam_strobe_cycles_remaining > 0,
        high_beam_strobe_cycles_remaining=state.high_beam_strobe_cycles_remaining,
        high_beam_next_transition_at=state.high_beam_next_transition_at,
    )


def initial_effects(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> tuple[ApplicationEffect, ...]:
    """Return the complete output projection for synchronization."""

    return (
        button_led_effect(state),
        steering_command(state, config, active_definition),
    )


def _steering_projection(
    state: ApplicationState,
    config: SteeringConfig,
) -> tuple[SteeringMode, int, bool]:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SteeringMode.MANUAL, steering.previous.manual_level, True
    return steering.mode, steering.manual_level, False


def _engine_value(
    value: int | float | None,
    observed_at: float | None,
    evaluated_at: float,
    config: EngineTelemetryConfig,
) -> EngineTelemetryValue:
    if observed_at is None:
        return EngineTelemetryValue(None, EngineTelemetryStatus.NEVER_OBSERVED)
    if evaluated_at - observed_at > config.timeout_s:
        return EngineTelemetryValue(None, EngineTelemetryStatus.STALE)
    return EngineTelemetryValue(value, EngineTelemetryStatus.VALID)
