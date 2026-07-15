"""Version 1 Socket.IO live-state payloads sourced from service snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast

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
    interpolation: Literal["linear-v1", "monotone-cubic-v1"]
    points: tuple[SteeringCurvePoint, ...]


class ActiveSteeringCurveState(LiveModel):
    definition: SteeringCurveDefinition
    fingerprint: str
    activation_revision: int
    status: Literal["active", "activating", "activation_failed"]
    saved_profile_id: str | None
    saved_profile_revision: int | None
    supported_interpolations: tuple[Literal["linear-v1", "monotone-cubic-v1"], ...]


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
    connected: bool
    fault: RuntimeFaultState | None
    received_frames: int = Field(ge=0)
    decoded_frames: int = Field(ge=0)
    ignored_frames: int = Field(ge=0)
    malformed_frames: int = Field(ge=0)
    effects_sent: int = Field(ge=0)
    effects_dropped: int = Field(ge=0)
    effects_rate_limited: int = Field(ge=0)
    effects_failed: int = Field(ge=0)


class InboxHealthState(LiveModel):
    depth: int = Field(ge=0)
    capacity: int = Field(gt=0)
    maximum_depth: int = Field(ge=0)
    current_latency_s: float = Field(ge=0)
    maximum_latency_s: float = Field(ge=0)
    latency_warning: bool
    latency_warning_count: int = Field(ge=0)
    overflow_latched: bool


class DeviceHealthState(LiveModel):
    id: Literal["button_pad"]
    source_mode: Literal["physical", "emulated", "observer"]
    connected: bool | None
    fault: RuntimeFaultState | None
    output_fault: str | None


class SteeringCapabilityHealthState(LiveModel):
    present: bool
    fault: RuntimeFaultState | None
    effects_sent: int = Field(ge=0)
    effects_dropped: int = Field(ge=0)
    effects_failed: int = Field(ge=0)


class PersistenceHealthState(LiveModel):
    available: bool
    fault: str | None


class PublisherHealthState(LiveModel):
    running: bool
    healthy: bool
    failures: int = Field(ge=0)
    published_by_event: dict[str, int]
    coalesced_by_event: dict[str, int]
    dropped_by_event: dict[str, int]
    active_sockets: int = Field(ge=0)
    trace_subscribers: int = Field(ge=0)
    trace_ring_length: int = Field(ge=0)
    trace_ring_capacity: int = Field(gt=0)
    transport_queue_saturations: int = Field(ge=0)
    fault: str | None


class FaultSummaryState(LiveModel):
    kind: str
    monotonic_s: float | None
    message: str


class ControllerHealthState(LiveModel):
    lifecycle: Literal["created", "running", "stopped"]
    ready: bool
    fatal: bool
    networks: tuple[NetworkHealthState, ...]
    inbox: InboxHealthState
    devices: tuple[DeviceHealthState, ...]
    steering: SteeringCapabilityHealthState
    persistence: PersistenceHealthState
    publisher: PublisherHealthState
    last_fatal_fault: FaultSummaryState | None
    last_non_fatal_fault: FaultSummaryState | None


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
    engine = snapshot.application.engine
    return EngineState(
        rpm=EngineTelemetryValue(value=engine.rpm.value, status=engine.rpm.status.value),
        oil_temperature_c=EngineTelemetryValue(
            value=engine.oil_temperature_c.value,
            status=engine.oil_temperature_c.status.value,
        ),
        coolant_temperature_c=EngineTelemetryValue(
            value=engine.coolant_temperature_c.value,
            status=engine.coolant_temperature_c.status.value,
        ),
    )


def steering_state(snapshot: ControllerServiceSnapshot) -> SteeringState:
    application = snapshot.application
    active = application.active_steering_curve
    return SteeringState(
        mode=application.steering_mode.value,
        manual_assistance_level=application.manual_assistance_level,
        maximum_assistance_active=application.maximum_assistance_active,
        active_curve=ActiveSteeringCurveState(
            definition=SteeringCurveDefinition(
                schema_version=cast(Literal[1], active.definition.schema_version),
                interpolation=active.definition.interpolation.value,
                points=tuple(
                    SteeringCurvePoint(
                        speed_deci_kph=point.speed_deci_kph,
                        assistance_per_mille=point.assistance_per_mille,
                    )
                    for point in active.definition.points
                ),
            ),
            fingerprint=active.fingerprint,
            activation_revision=active.activation_revision,
            status=application.steering_curve_activation_status.value,
            saved_profile_id=active.saved_profile_id,
            saved_profile_revision=active.saved_profile_revision,
            supported_interpolations=tuple(
                item.value
                for item in application.supported_steering_curve_interpolations
            ),
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
            DeviceState.model_validate(
                {
                    "id": device.id.value,
                    "label": device.label,
                    "source_mode": device.source_mode.value,
                    "connected": device.connected,
                    "last_seen_monotonic_s": device.last_seen_monotonic_s,
                    "desired_led_colours": device.desired_led_colours,
                    "observed_led_colours": device.observed_led_colours,
                    "last_output_fault": device.last_output_fault,
                }
            )
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
            else SteeringActuatorState.model_validate(
                {
                    "effective_assistance": steering.effective_assistance,
                    "last_command_reason": steering.last_command_reason,
                    "watchdog_timed_out": steering.watchdog_timed_out,
                }
            )
        ),
    )


def health_state(snapshot: ControllerServiceSnapshot) -> ControllerHealthState:
    health = snapshot.diagnostics.health
    effects = snapshot.adapter.effects
    effect_sent = dict(effects.sent)
    effect_dropped = dict(effects.dropped)
    effect_rate_limited = dict(effects.rate_limited)
    effect_failed = dict(effects.failed)
    connected = {item.network: item.connected for item in snapshot.adapter.networks}
    device_faults = {item.role: item.fault for item in health.devices}
    fatal_faults = [
        fault
        for fault in (
            health.inbox_overflow_fault,
            health.steering_actuator_fault,
            *(item.fault for item in health.networks),
        )
        if fault is not None
        and fault.kind.value
        in {"inbox_overflow", "steering_actuator", "can_reader", "can_effect_execution"}
    ]
    non_fatal_faults = [
        fault
        for fault in (
            *(item.fault for item in health.networks),
            *(item.fault for item in health.devices),
        )
        if fault is not None
        and fault.kind.value
        not in {"inbox_overflow", "steering_actuator", "can_reader", "can_effect_execution"}
    ]
    external_non_fatal = (
        ("persistence", snapshot.service.persistence.fault)
        if snapshot.service.persistence.fault is not None
        else (
            ("publisher", snapshot.service.publisher.fault)
            if snapshot.service.publisher.fault is not None
            else None
        )
    )
    return ControllerHealthState(
        lifecycle=snapshot.diagnostics.lifecycle.value,
        ready=snapshot.service.ready,
        fatal=health.fatal,
        networks=tuple(
            NetworkHealthState(
                network=network.network.value,
                connected=connected.get(network.network, False),
                fault=_fault_state(network.fault),
                received_frames=network.received_frames,
                decoded_frames=network.decoded_frames,
                ignored_frames=network.ignored_frames,
                malformed_frames=network.malformed_frames,
                effects_sent=effect_sent.get(network.network, 0),
                effects_dropped=effect_dropped.get(network.network, 0),
                effects_rate_limited=effect_rate_limited.get(network.network, 0),
                effects_failed=effect_failed.get(network.network, 0),
            )
            for network in health.networks
        ),
        inbox=InboxHealthState.model_validate(snapshot.service.inbox, from_attributes=True),
        devices=tuple(
            DeviceHealthState(
                id=device.id.value,
                source_mode=cast(
                    Literal["physical", "emulated", "observer"],
                    device.source_mode.value,
                ),
                connected=device.connected,
                fault=_fault_state(device_faults.get(device.id)),
                output_fault=device.last_output_fault,
            )
            for device in snapshot.adapter.devices
        ),
        steering=SteeringCapabilityHealthState(
            present=snapshot.adapter.steering is not None,
            fault=_fault_state(health.steering_actuator_fault),
            effects_sent=effects.steering_sent,
            effects_dropped=effects.steering_dropped,
            effects_failed=effects.steering_failed,
        ),
        persistence=PersistenceHealthState.model_validate(
            snapshot.service.persistence,
            from_attributes=True,
        ),
        publisher=PublisherHealthState(
            running=snapshot.service.publisher.running,
            healthy=snapshot.service.publisher.healthy,
            failures=snapshot.service.publisher.failures,
            published_by_event=dict(snapshot.service.publisher.published_by_event),
            coalesced_by_event=dict(snapshot.service.publisher.coalesced_by_event),
            dropped_by_event=dict(snapshot.service.publisher.dropped_by_event),
            active_sockets=snapshot.service.publisher.active_sockets,
            trace_subscribers=snapshot.service.publisher.trace_subscribers,
            trace_ring_length=snapshot.service.publisher.trace_ring_length,
            trace_ring_capacity=snapshot.service.publisher.trace_ring_capacity,
            transport_queue_saturations=(
                snapshot.service.publisher.transport_queue_saturations
            ),
            fault=snapshot.service.publisher.fault,
        ),
        last_fatal_fault=_fault_summary(max(fatal_faults, key=lambda item: item.occurred_at))
        if fatal_faults
        else None,
        last_non_fatal_fault=(
            _fault_summary(max(non_fatal_faults, key=lambda item: item.occurred_at))
            if non_fatal_faults
            else (
                None
                if external_non_fatal is None
                else FaultSummaryState(
                    kind=external_non_fatal[0],
                    monotonic_s=None,
                    message=external_non_fatal[1],
                )
            )
        ),
    )


def _fault_summary(fault: object) -> FaultSummaryState:
    from e87canbus.runtime import RuntimeFault

    if not isinstance(fault, RuntimeFault):
        raise TypeError(f"unexpected runtime fault: {fault!r}")
    return FaultSummaryState(
        kind=fault.kind.value,
        monotonic_s=fault.occurred_at,
        message=fault.message,
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
