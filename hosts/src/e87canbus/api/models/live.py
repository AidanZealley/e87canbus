"""Shared coordinator live projections."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.domain.buttons.pad import BUTTON_PAD_PROGRAM_ENCODING
from e87canbus.domain.steering.curves import STEERING_CURVE_V1_SPEEDS_DECI_KPH
from e87canbus.kernel import StateTopic
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
    status: Literal["active", "activating", "activation_failed"]
    saved_profile_id: str | None
    saved_profile_revision: int | None


class ServotronicState(LiveModel):
    effective_assistance: float
    last_command_reason: (
        Literal[
            "auto",
            "manual",
            "maximum",
            "speed_never_observed",
            "speed_stale",
            "can_reader_failure",
            "inbox_overflow",
            "shutdown",
        ]
        | None
    )
    watchdog_timed_out: bool
    active_curve_source: Literal["builtin_fallback", "coordinator_ram"] | None = None
    active_curve_revision: int | None = None
    active_curve_crc32: int | None = None
    observed_speed_kph: float | None = None
    speed_fresh: bool | None = None
    pwm_duty: int | None = None
    inhibit_reason: str | None = None


class SteeringState(LiveModel):
    mode: Literal["auto", "manual"]
    manual_assistance_level: int = Field(ge=0)
    manual_assistance_level_count: int = Field(gt=0)
    maximum_assistance_active: bool
    active_curve: ActiveSteeringCurveState
    servotronic: ServotronicState | None
    curve_activation_available: bool


ButtonPadProgramByte = Annotated[int, Field(ge=0, le=255)]
ButtonPadCommand = Annotated[tuple[ButtonPadProgramByte, ...], Field(min_length=16, max_length=16)]


class ButtonPadProgramState(LiveModel):
    encoding: Literal["e87-button-pad-v2"] = BUTTON_PAD_PROGRAM_ENCODING
    generation: int = Field(ge=0)
    commands: tuple[ButtonPadCommand, ...] = Field(min_length=1, max_length=16)


class ButtonsState(LiveModel):
    program: ButtonPadProgramState
    active_profile_id: str = Field(min_length=1)
    active_profile_revision: int | None = Field(default=None, ge=1)


class LightingState(LiveModel):
    high_beam_enabled: bool
    high_beam_strobe_active: bool
    high_beam_strobe_cycles_remaining: int = Field(ge=0)
    observed_high_beam_enabled: bool | None


class RuntimeFaultState(LiveModel):
    kind: Literal[
        "can_reader",
        "can_effect_execution",
        "steering_actuator",
        "inbox_overflow",
        "device_adapter",
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


class DeviceHealthState(LiveModel):
    role: Literal["button_pad", "servotronic_controller"]
    fault: RuntimeFaultState | None


class SteeringCapabilityHealthState(LiveModel):
    fault: RuntimeFaultState | None


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
            status=application.steering_curve_activation_status.value,
            saved_profile_id=active.saved_profile_id,
            saved_profile_revision=active.saved_profile_revision,
        ),
        servotronic=(
            None
            if snapshot.adapter.servotronic is None
            else ServotronicState.model_validate(
                snapshot.adapter.servotronic,
                from_attributes=True,
            )
        ),
        curve_activation_available=application.curve_activation_available,
    )


def buttons_state(snapshot: ControllerLoopSnapshot) -> ButtonsState:
    return ButtonsState(
        program=ButtonPadProgramState(
            generation=dict(snapshot.topic_revisions)[StateTopic.BUTTONS],
            commands=tuple(
                tuple(payload) for payload in snapshot.application.button_pad_program.payloads
            ),
        ),
        active_profile_id=snapshot.application.active_button_profile_id,
        active_profile_revision=snapshot.application.active_button_profile_revision,
    )


def lighting_state(snapshot: ControllerLoopSnapshot) -> LightingState:
    application = snapshot.application
    lighting = snapshot.adapter.lighting
    return LightingState(
        high_beam_enabled=application.high_beam_enabled,
        high_beam_strobe_active=application.high_beam_strobe_active,
        high_beam_strobe_cycles_remaining=application.high_beam_strobe_cycles_remaining,
        observed_high_beam_enabled=(None if lighting is None else lighting.high_beam_enabled),
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
