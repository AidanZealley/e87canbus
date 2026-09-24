"""The immutable desired-state and vehicle telemetry snapshot.

``snapshot`` composes the complete read-only view published to adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.config import EngineTelemetryConfig, SteeringConfig
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.buttons.scene import ResolvedButton, resolve_button_pad
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.domain.steering.curves import (
    ActiveSteeringCurve,
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
    active_button_profile_id: str
    active_button_profile_revision: int | None
    button_pad: tuple[ResolvedButton, ...] = ()


def snapshot(
    state: ApplicationState,
    config: SteeringConfig,
    engine_config: EngineTelemetryConfig,
    active_curve: ActiveSteeringCurve,
    active_button_profile_id: str,
    saved_button_profile_revision: int | None,
    button_profile: ActiveButtonProfile | None = None,
) -> ApplicationSnapshot:
    """Project read-only application state."""

    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
        manual_assistance_level_count=config.manual_level_count,
        maximum_assistance_active=maximum_active,
        speed_valid=(
            sample is not None
            and state.speed_evaluated_at - sample.observed_at <= config.speed_timeout_s
        ),
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
        active_button_profile_id=active_button_profile_id,
        active_button_profile_revision=saved_button_profile_revision,
        button_pad=resolve_button_pad(state, button_profile) if button_profile else (),
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
