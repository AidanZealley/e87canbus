from fastapi import APIRouter, Request

from e87canbus.device import DeviceRole
from e87canbus.simulation.api.internal.commands import run_command
from e87canbus.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.simulation.api.models.devices import (
    SimulationDeviceProtocolVersionRequest,
    SimulationDeviceStatusCodeRequest,
)
from e87canbus.simulation.commands import (
    ConnectSimulatedDevice,
    DisconnectSimulatedDevice,
    RebootSimulatedDevice,
    SetSimulatedDeviceProtocolVersion,
    SetSimulatedDeviceStatusCode,
    TapButton,
)

router = APIRouter(
    prefix="/api/dev/simulation/devices",
    tags=["development simulation: devices"],
)


@router.post("/button-pad/buttons/{button_index}/tap")
async def tap_button(
    request: Request, button_index: int
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, TapButton(button_index))


@router.post("/{role}/connect")
async def connect_device(
    request: Request, role: DeviceRole
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, ConnectSimulatedDevice(role))


@router.post("/{role}/disconnect")
async def disconnect_device(
    request: Request, role: DeviceRole
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, DisconnectSimulatedDevice(role))


@router.post("/{role}/reboot")
async def reboot_device(
    request: Request, role: DeviceRole
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, RebootSimulatedDevice(role))


@router.put("/{role}/protocol-version")
async def set_device_protocol_version(
    request: Request,
    role: DeviceRole,
    body: SimulationDeviceProtocolVersionRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetSimulatedDeviceProtocolVersion(role, body.protocol_version),
    )


@router.put("/{role}/status-code")
async def set_device_status_code(
    request: Request,
    role: DeviceRole,
    body: SimulationDeviceStatusCodeRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetSimulatedDeviceStatusCode(role, body.status_code),
    )
