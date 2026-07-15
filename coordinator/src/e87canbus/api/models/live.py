"""Version 1 Socket.IO live-state payloads sourced from service snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.service import ControllerServiceSnapshot

PROTOCOL_VERSION: Literal[1] = 1
LedCode = Annotated[int, Field(ge=0, le=5)]
LedSnapshot = Annotated[tuple[LedCode, ...], Field(min_length=16, max_length=16)]


class LiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TopicRevisions(LiveModel):
    vehicle: int = Field(ge=0)
    engine: int = Field(ge=0)
    steering: int = Field(ge=0)
    buttons: int = Field(ge=0)
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
    points: tuple[SteeringCurvePoint, ...]


class ActiveSteeringCurveState(LiveModel):
    definition: SteeringCurveDefinition
    fingerprint: str
    activation_revision: int
    status: Literal["active", "activating", "activation_failed"]
    saved_profile_id: str | None
    saved_profile_revision: int | None


class SteeringState(LiveModel):
    mode: Literal["auto", "manual"]
    manual_assistance_level: int = Field(ge=0)
    maximum_assistance_active: bool
    active_curve: ActiveSteeringCurveState


class ButtonsState(LiveModel):
    led_colours: LedSnapshot


class DeviceState(LiveModel):
    id: Literal["button_pad"]
    label: str
    source_mode: Literal["physical", "emulated", "observer"]
    connected: bool | None
    last_seen_monotonic_s: float | None
    desired_led_colours: LedSnapshot
    observed_led_colours: LedSnapshot | None
    last_output_fault: str | None


class NetworkState(LiveModel):
    id: Literal["kcan", "ptcan", "fcan"]
    label: str
    interface: str
    bitrate: int = Field(gt=0)
    connected: bool
    nodes: tuple[str, ...]


class SteeringActuatorState(LiveModel):
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


class DevicesState(LiveModel):
    devices: tuple[DeviceState, ...]
    networks: tuple[NetworkState, ...]
    steering_controller: SteeringActuatorState | None


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
    id: Literal["button_pad"]
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
    | DevicesState
    | ControllerHealthState
    | TraceBatchData
)


class LiveEnvelope(LiveModel):
    protocol_version: Literal[1] = PROTOCOL_VERSION
    boot_id: str = Field(min_length=1)
    revision: int = Field(ge=0)
    emitted_at: datetime
    data: LiveData


def snapshot_data(snapshot: ControllerServiceSnapshot) -> ControllerSnapshotData:
    return ControllerSnapshotData(
        topic_revisions=TopicRevisions(**dict(snapshot.topic_revisions)),
        simulation_session_id=snapshot.adapter.simulation_session_id,
        vehicle=vehicle_state(snapshot),
        engine=engine_state(snapshot),
        steering=steering_state(snapshot),
        buttons=buttons_state(snapshot),
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
    )


def buttons_state(snapshot: ControllerServiceSnapshot) -> ButtonsState:
    return ButtonsState(
        led_colours=snapshot.adapter.led_colours,
    )


def devices_state(snapshot: ControllerServiceSnapshot) -> DevicesState:
    steering = snapshot.adapter.steering
    return DevicesState(
        devices=tuple(
            DeviceState.model_validate(device, from_attributes=True)
            for device in snapshot.adapter.devices
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
        steering_controller=(
            None
            if steering is None
            else SteeringActuatorState.model_validate(steering, from_attributes=True)
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
                id=device.id.value,
                fault=_fault_state(device_faults.get(device.id)),
            )
            for device in snapshot.adapter.devices
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
            resource_changes_dropped=(
                snapshot.service.publisher.resource_changes_dropped
            ),
            transport_queue_saturations=(
                snapshot.service.publisher.transport_queue_saturations
            ),
            fault=snapshot.service.publisher.fault,
        ),
    )


def _fault_state(fault: object) -> RuntimeFaultState | None:
    from e87canbus.runtime import RuntimeFault

    if fault is None:
        return None
    if not isinstance(fault, RuntimeFault):
        raise TypeError(f"unexpected runtime fault: {fault!r}")
    return RuntimeFaultState(
        kind=fault.kind.value,
        monotonic_s=fault.occurred_at,
        message=fault.message,
    )
