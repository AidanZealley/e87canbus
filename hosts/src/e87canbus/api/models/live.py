"""Shared coordinator live projections."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.domain.steering.curves import STEERING_CURVE_V1_SPEEDS_DECI_KPH
from e87canbus.service import ControllerLoopSnapshot

STEERING_CURVE_POINT_COUNT = len(STEERING_CURVE_V1_SPEEDS_DECI_KPH)


class LiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VehicleState(LiveModel):
    speed_kph: float
    speed_valid: bool


class EngineTelemetryValue(LiveModel):
    value: int | float | None
    status: Literal["valid", "never_observed", "stale"]


class EngineState(LiveModel):
    rpm: EngineTelemetryValue
    oil_temperature_c: EngineTelemetryValue
    coolant_temperature_c: EngineTelemetryValue


class SteeringCurvePoint(LiveModel):
    speed_deci_kph: int
    assistance_per_mille: int


class SteeringCurveDefinition(LiveModel):
    schema_version: Literal[1]
    points: tuple[SteeringCurvePoint, ...] = Field(
        min_length=STEERING_CURVE_POINT_COUNT,
        max_length=STEERING_CURVE_POINT_COUNT,
    )


class ActiveSteeringCurveState(LiveModel):
    definition: SteeringCurveDefinition
    fingerprint: str
    activation_revision: int
    saved_profile_id: str | None
    saved_profile_revision: int | None


class SteeringState(LiveModel):
    mode: Literal["auto", "manual"]
    manual_assistance_level: int = Field(ge=0)
    manual_assistance_level_count: int = Field(gt=0)
    maximum_assistance_active: bool
    active_curve: ActiveSteeringCurveState


class ButtonsState(LiveModel):
    active_profile_id: str = Field(min_length=1)
    active_profile_revision: int | None = Field(default=None, ge=1)


class RuntimeFaultState(LiveModel):
    kind: Literal[
        "can_reader",
        "inbox_overflow",
    ]
    monotonic_s: float
    message: str


class NetworkHealthState(LiveModel):
    network: Literal["kcan", "ptcan", "fcan"]
    fault: RuntimeFaultState | None


class InboxHealthState(LiveModel):
    depth: int = Field(ge=0)
    capacity: int = Field(gt=0)
    current_latency_s: float = Field(ge=0)
    latency_warning: bool
    overflow_latched: bool


class PersistenceHealthState(LiveModel):
    available: bool
    fault: str | None


def vehicle_state(snapshot: ControllerLoopSnapshot) -> VehicleState:
    return VehicleState(
        speed_kph=snapshot.application.vehicle_speed_kph,
        speed_valid=snapshot.application.speed_valid,
    )


def engine_state(snapshot: ControllerLoopSnapshot) -> EngineState:
    return EngineState.model_validate(snapshot.application.engine, from_attributes=True)


def steering_state(snapshot: ControllerLoopSnapshot) -> SteeringState:
    application = snapshot.application
    active = application.active_steering_curve
    return SteeringState(
        mode=application.steering_mode.value,
        manual_assistance_level=application.manual_assistance_level,
        manual_assistance_level_count=application.manual_assistance_level_count,
        maximum_assistance_active=application.maximum_assistance_active,
        active_curve=ActiveSteeringCurveState(
            definition=SteeringCurveDefinition.model_validate(
                active.definition,
                from_attributes=True,
            ),
            fingerprint=active.fingerprint,
            activation_revision=active.activation_revision,
            saved_profile_id=active.saved_profile_id,
            saved_profile_revision=active.saved_profile_revision,
        ),
    )


def buttons_state(snapshot: ControllerLoopSnapshot) -> ButtonsState:
    return ButtonsState(
        active_profile_id=snapshot.application.active_button_profile_id,
        active_profile_revision=snapshot.application.active_button_profile_revision,
    )


def fault_state(fault: object) -> RuntimeFaultState | None:
    from e87canbus.kernel import RuntimeFault

    if fault is None:
        return None
    if not isinstance(fault, RuntimeFault):
        raise TypeError(f"unexpected runtime fault: {fault!r}")
    return RuntimeFaultState(
        kind=fault.kind.value,
        monotonic_s=fault.occurred_at,
        message=fault.message,
    )
