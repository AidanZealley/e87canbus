from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.domain.devices.catalogue import DeviceRole
from e87canbus.runners.simulation.api.internal.commands import run_command
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.api.models.devices import (
    SimulationDeviceProtocolVersionRequest,
    SimulationDeviceStatusCodeRequest,
)
from e87canbus.runners.simulation.commands import (
    ConnectSimulatedDevice,
    DisconnectSimulatedDevice,
    RebootSimulatedDevice,
    SetSimulatedDeviceProtocolVersion,
    SetSimulatedDeviceStatusCode,
)

router = APIRouter(
    prefix="/api/dev/simulation/devices",
    tags=["development simulation: devices"],
)


@router.post(
    "/{role}/connect",
    operation_id="connectSimulationDevice",
    responses=api_problem_responses(409, 422, 503),
)
async def connect_device(request: Request, role: DeviceRole) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, ConnectSimulatedDevice(role))


@router.post(
    "/{role}/disconnect",
    operation_id="disconnectSimulationDevice",
    responses=api_problem_responses(409, 422, 503),
)
async def disconnect_device(request: Request, role: DeviceRole) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, DisconnectSimulatedDevice(role))


@router.post(
    "/{role}/reboot",
    operation_id="rebootSimulationDevice",
    responses=api_problem_responses(409, 422, 503),
)
async def reboot_device(request: Request, role: DeviceRole) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, RebootSimulatedDevice(role))


@router.put(
    "/{role}/protocol-version",
    operation_id="setSimulationDeviceProtocolVersion",
    responses=api_problem_responses(409, 422, 503),
)
async def set_device_protocol_version(
    request: Request,
    role: DeviceRole,
    body: SimulationDeviceProtocolVersionRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetSimulatedDeviceProtocolVersion(role, body.protocol_version),
    )


@router.put(
    "/{role}/status-code",
    operation_id="setSimulationDeviceStatusCode",
    responses=api_problem_responses(409, 422, 503),
)
async def set_device_status_code(
    request: Request,
    role: DeviceRole,
    body: SimulationDeviceStatusCodeRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetSimulatedDeviceStatusCode(role, body.status_code),
    )
