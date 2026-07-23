"""Version 1 Socket.IO live-state payloads sourced from service snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.button_pad import BUTTON_PAD_PROGRAM_ENCODING
from e87canbus.device import DeviceRole
from e87canbus.features.steering import STEERING_CURVE_V1_SPEEDS_DECI_KPH
from e87canbus.kernel import StateTopic
from e87canbus.service import ControllerServiceSnapshot

PROTOCOL_VERSION: Literal[1] = 1
STEERING_CURVE_POINT_COUNT = len(STEERING_CURVE_V1_SPEEDS_DECI_KPH)


class LiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TopicRevisions(LiveModel):
    vehicle: int = Field(ge=0)
    engine: int = Field(ge=0)
    steering: int = Field(ge=0)
    buttons: int = Field(ge=0)
    lighting: int = Field(ge=0)
    devices: int = Field(ge=0)
    health: int = Field(ge=0)


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


class LightingState(LiveModel):
    high_beam_enabled: bool
    high_beam_strobe_active: bool
    high_beam_strobe_cycles_remaining: int = Field(ge=0)
    observed_high_beam_enabled: bool | None


class DeviceRegistryEntryState(LiveModel):
    role: Literal["button_pad", "servotronic_controller"]
    label: str
    device_id: int = Field(ge=0, le=0xFFFF)
    source_mode: Literal["physical", "emulated", "disabled"]
    status: Literal[
        "disabled",
        "not_found",
        "pending",
        "active",
        "stale",
        "incompatible",
        "fault",
    ]
    protocol_version: int | None
    device_session_id: int | None
    last_status_code: int | None
    last_transition_monotonic_s: float | None


class DeviceRegistryState(LiveModel):
    button_pad: DeviceRegistryEntryState
    servotronic_controller: DeviceRegistryEntryState


class NetworkState(LiveModel):
    id: Literal["kcan", "ptcan", "fcan"]
    label: str
    interface: str
    bitrate: int = Field(gt=0)
    connected: bool
    nodes: tuple[str, ...]


class DevicesState(LiveModel):
    registry: DeviceRegistryState
    networks: tuple[NetworkState, ...]


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


class PublisherHealthState(LiveModel):
    running: bool
    failures: int = Field(ge=0)
    trace_rows_dropped: int = Field(ge=0)
    resource_changes_dropped: int = Field(ge=0)
    transport_queue_saturations: int = Field(ge=0)
    fault: str | None


class ControllerHealthState(LiveModel):
    ready: bool
    fatal: bool
    networks: tuple[NetworkHealthState, ...]
    inbox: InboxHealthState
    devices: tuple[DeviceHealthState, ...]
    steering: SteeringCapabilityHealthState
    persistence: PersistenceHealthState
    publisher: PublisherHealthState


class ControllerSnapshotData(LiveModel):
    topic_revisions: TopicRevisions
    simulation_session_id: int | None
    vehicle: VehicleState
    engine: EngineState
    steering: SteeringState
    buttons: ButtonsState
    lighting: LightingState
    devices: DevicesState
    health: ControllerHealthState


class TraceRow(LiveModel):
    type: Literal["frame"] = "frame"
    session_id: int
    sequence: int = Field(ge=1)
    network: Literal["kcan", "ptcan", "fcan"]
    source: str
    arbitration_id: int = Field(ge=0)
    arbitration_id_hex: str
    data_hex: str
    is_extended_id: bool
    monotonic_s: float


class TraceBatchData(LiveModel):
    rows: tuple[TraceRow, ...]


LiveData = (
    ControllerSnapshotData
    | VehicleState
    | EngineState
    | SteeringState
    | ButtonsState
    | LightingState
    | DevicesState
    | ControllerHealthState
    | TraceBatchData
)


LivePayload = TypeVar("LivePayload", bound=LiveModel)


class LiveEnvelope(LiveModel, Generic[LivePayload]):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    boot_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    emitted_at: datetime
    data: LivePayload


def snapshot_data(snapshot: ControllerServiceSnapshot) -> ControllerSnapshotData:
    return ControllerSnapshotData(
        topic_revisions=TopicRevisions(**dict(snapshot.topic_revisions)),
        simulation_session_id=snapshot.adapter.simulation_session_id,
        vehicle=vehicle_state(snapshot),
        engine=engine_state(snapshot),
        steering=steering_state(snapshot),
        buttons=buttons_state(snapshot),
        lighting=lighting_state(snapshot),
        devices=devices_state(snapshot),
        health=health_state(snapshot),
    )


def vehicle_state(snapshot: ControllerServiceSnapshot) -> VehicleState:
    return VehicleState(
        speed_kph=snapshot.application.vehicle_speed_kph,
        speed_valid=snapshot.application.speed_valid,
    )


def engine_state(snapshot: ControllerServiceSnapshot) -> EngineState:
    return EngineState.model_validate(snapshot.application.engine, from_attributes=True)


def steering_state(snapshot: ControllerServiceSnapshot) -> SteeringState:
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


def buttons_state(snapshot: ControllerServiceSnapshot) -> ButtonsState:
    return ButtonsState(
        program=ButtonPadProgramState(
            generation=dict(snapshot.topic_revisions)[StateTopic.BUTTONS],
            commands=tuple(
                tuple(payload) for payload in snapshot.application.button_pad_program.payloads
            ),
        ),
    )


def lighting_state(snapshot: ControllerServiceSnapshot) -> LightingState:
    application = snapshot.application
    lighting = snapshot.adapter.lighting
    return LightingState(
        high_beam_enabled=application.high_beam_enabled,
        high_beam_strobe_active=application.high_beam_strobe_active,
        high_beam_strobe_cycles_remaining=application.high_beam_strobe_cycles_remaining,
        observed_high_beam_enabled=(None if lighting is None else lighting.high_beam_enabled),
    )


def devices_state(snapshot: ControllerServiceSnapshot) -> DevicesState:
    registry = {
        entry.role.value: DeviceRegistryEntryState.model_validate(
            entry,
            from_attributes=True,
        )
        for entry in snapshot.adapter.registry
    }
    return DevicesState(
        registry=DeviceRegistryState(
            button_pad=registry[DeviceRole.BUTTON_PAD.value],
            servotronic_controller=registry[DeviceRole.SERVOTRONIC_CONTROLLER.value],
        ),
        networks=tuple(
            NetworkState(
                id=network.network.value,
                label=network.label,
                interface=network.interface,
                bitrate=network.bitrate,
                connected=network.connected,
                nodes=network.nodes,
            )
            for network in snapshot.adapter.networks
        ),
    )


def health_state(snapshot: ControllerServiceSnapshot) -> ControllerHealthState:
    health = snapshot.diagnostics.health
    device_faults = {item.role: item.fault for item in health.devices}
    return ControllerHealthState(
        ready=snapshot.service.ready,
        fatal=health.fatal,
        networks=tuple(
            NetworkHealthState(
                network=network.network.value,
                fault=_fault_state(network.fault),
            )
            for network in health.networks
        ),
        inbox=InboxHealthState.model_validate(snapshot.service.inbox, from_attributes=True),
        devices=tuple(
            DeviceHealthState(
                role=device.role.value,
                fault=_fault_state(device_faults.get(device.role)),
            )
            for device in health.devices
        ),
        steering=SteeringCapabilityHealthState(
            fault=_fault_state(health.steering_actuator_fault),
        ),
        persistence=PersistenceHealthState.model_validate(
            snapshot.service.persistence,
            from_attributes=True,
        ),
        publisher=PublisherHealthState(
            running=snapshot.service.publisher.running,
            failures=snapshot.service.publisher.failures,
            trace_rows_dropped=snapshot.service.publisher.trace_rows_dropped,
            resource_changes_dropped=(snapshot.service.publisher.resource_changes_dropped),
            transport_queue_saturations=(snapshot.service.publisher.transport_queue_saturations),
            fault=snapshot.service.publisher.fault,
        ),
    )


def _fault_state(fault: object) -> RuntimeFaultState | None:
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
