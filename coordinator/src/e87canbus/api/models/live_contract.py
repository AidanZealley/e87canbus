"""Closed, versioned Socket.IO event contract shared by runtime and code generation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from e87canbus.api.models.live import (
    ButtonsState,
    ControllerHealthState,
    ControllerSnapshotData,
    DevicesState,
    EngineState,
    LightingState,
    SteeringState,
    TraceBatchData,
    VehicleState,
)
from e87canbus.api.models.resources import ResourceChangedEvent


class ServerEvent(StrEnum):
    CONTROLLER_SNAPSHOT = "controller.snapshot"
    VEHICLE_STATE = "vehicle.state"
    ENGINE_STATE = "engine.state"
    STEERING_STATE = "steering.state"
    BUTTONS_STATE = "buttons.state"
    LIGHTING_STATE = "lighting.state"
    DEVICES_STATE = "devices.state"
    CONTROLLER_HEALTH = "controller.health"
    RESOURCES_CHANGED = "resources.changed"
    TRACE_BATCH = "trace.batch"


class ClientEvent(StrEnum):
    CONTROLLER_RESYNC = "controller.resync"
    TRACE_SUBSCRIBE = "trace.subscribe"
    TRACE_UNSUBSCRIBE = "trace.unsubscribe"


@dataclass(frozen=True)
class EventContract:
    name: ServerEvent | ClientEvent
    direction: Literal["server_to_client", "client_to_server"]
    payload: type[BaseModel] | None
    enveloped: bool = False


EVENT_CONTRACTS = (
    EventContract(
        ServerEvent.CONTROLLER_SNAPSHOT,
        "server_to_client",
        ControllerSnapshotData,
        True,
    ),
    EventContract(ServerEvent.VEHICLE_STATE, "server_to_client", VehicleState, True),
    EventContract(ServerEvent.ENGINE_STATE, "server_to_client", EngineState, True),
    EventContract(ServerEvent.STEERING_STATE, "server_to_client", SteeringState, True),
    EventContract(ServerEvent.BUTTONS_STATE, "server_to_client", ButtonsState, True),
    EventContract(ServerEvent.LIGHTING_STATE, "server_to_client", LightingState, True),
    EventContract(ServerEvent.DEVICES_STATE, "server_to_client", DevicesState, True),
    EventContract(ServerEvent.CONTROLLER_HEALTH, "server_to_client", ControllerHealthState, True),
    EventContract(ServerEvent.RESOURCES_CHANGED, "server_to_client", ResourceChangedEvent),
    EventContract(ServerEvent.TRACE_BATCH, "server_to_client", TraceBatchData, True),
    EventContract(ClientEvent.CONTROLLER_RESYNC, "client_to_server", None),
    EventContract(ClientEvent.TRACE_SUBSCRIBE, "client_to_server", None),
    EventContract(ClientEvent.TRACE_UNSUBSCRIBE, "client_to_server", None),
)

SERVER_EVENT_CONTRACTS = tuple(
    contract for contract in EVENT_CONTRACTS if contract.direction == "server_to_client"
)
CLIENT_EVENT_CONTRACTS = tuple(
    contract for contract in EVENT_CONTRACTS if contract.direction == "client_to_server"
)
