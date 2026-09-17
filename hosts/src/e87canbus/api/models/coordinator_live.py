"""Coordinator browser SSE event contract."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from e87canbus.api.models.live import (
    ButtonsState,
    DeviceHealthState,
    EngineState,
    InboxHealthState,
    LightingState,
    LiveModel,
    NetworkHealthState,
    PersistenceHealthState,
    SteeringCapabilityHealthState,
    SteeringState,
    VehicleState,
    buttons_state,
    engine_state,
    fault_state,
    lighting_state,
    steering_state,
    vehicle_state,
)
from e87canbus.api.models.resources import ResourceChangedEvent
from e87canbus.service import ControllerLoopSnapshot


class CoordinatorHealthState(LiveModel):
    ready: bool
    fatal: bool
    networks: tuple[NetworkHealthState, ...]
    inbox: InboxHealthState
    devices: tuple[DeviceHealthState, ...]
    steering: SteeringCapabilityHealthState
    persistence: PersistenceHealthState


class CoordinatorSnapshot(LiveModel):
    vehicle: VehicleState
    engine: EngineState
    steering: SteeringState
    buttons: ButtonsState
    lighting: LightingState
    health: CoordinatorHealthState


class SnapshotEvent(LiveModel):
    type: Literal["snapshot"]
    data: CoordinatorSnapshot


class VehicleEvent(LiveModel):
    type: Literal["vehicle"]
    data: VehicleState


class EngineEvent(LiveModel):
    type: Literal["engine"]
    data: EngineState


class SteeringEvent(LiveModel):
    type: Literal["steering"]
    data: SteeringState


class ButtonsEvent(LiveModel):
    type: Literal["buttons"]
    data: ButtonsState


class LightingEvent(LiveModel):
    type: Literal["lighting"]
    data: LightingState


class HealthEvent(LiveModel):
    type: Literal["health"]
    data: CoordinatorHealthState


class SettingsResourceChangedData(LiveModel):
    resource: Literal["settings"]
    id: None
    revision: int = Field(ge=1)


class ProfileResourceChangedData(LiveModel):
    resource: Literal["steering_profile", "button_profile"]
    id: str = Field(min_length=1)
    revision: int = Field(ge=1)


ResourceChangedData = Annotated[
    SettingsResourceChangedData | ProfileResourceChangedData,
    Field(discriminator="resource"),
]


class ResourceChangedSseEvent(LiveModel):
    type: Literal["resource.changed"]
    data: ResourceChangedData


CoordinatorLiveEvent = Annotated[
    SnapshotEvent
    | VehicleEvent
    | EngineEvent
    | SteeringEvent
    | ButtonsEvent
    | LightingEvent
    | HealthEvent
    | ResourceChangedSseEvent,
    Field(discriminator="type"),
]


def snapshot_event(snapshot: ControllerLoopSnapshot) -> SnapshotEvent:
    return SnapshotEvent(
        type="snapshot",
        data=CoordinatorSnapshot(
            vehicle=vehicle_state(snapshot),
            engine=engine_state(snapshot),
            steering=steering_state(snapshot),
            buttons=buttons_state(snapshot),
            lighting=lighting_state(snapshot),
            health=coordinator_health_state(snapshot),
        ),
    )


def resource_changed_event(event: ResourceChangedEvent) -> ResourceChangedSseEvent:
    data: ResourceChangedData
    if event.resource == "settings":
        data = SettingsResourceChangedData(
            resource=event.resource,
            id=None,
            revision=event.revision,
        )
    else:
        assert event.id is not None
        data = ProfileResourceChangedData(
            resource=event.resource,
            id=event.id,
            revision=event.revision,
        )
    return ResourceChangedSseEvent(
        type="resource.changed",
        data=data,
    )


def coordinator_health_state(snapshot: ControllerLoopSnapshot) -> CoordinatorHealthState:
    health = snapshot.diagnostics.health
    device_faults = {item.role: item.fault for item in health.devices}
    return CoordinatorHealthState(
        ready=snapshot.service.ready,
        fatal=health.fatal,
        networks=tuple(
            NetworkHealthState(
                network=network.network.value,
                fault=fault_state(network.fault),
            )
            for network in health.networks
        ),
        inbox=InboxHealthState.model_validate(snapshot.service.inbox, from_attributes=True),
        devices=tuple(
            DeviceHealthState(
                role=device.role.value,
                fault=fault_state(device_faults.get(device.role)),
            )
            for device in health.devices
        ),
        steering=SteeringCapabilityHealthState(
            fault=fault_state(health.steering_actuator_fault),
        ),
        persistence=PersistenceHealthState.model_validate(
            snapshot.service.persistence,
            from_attributes=True,
        ),
    )
