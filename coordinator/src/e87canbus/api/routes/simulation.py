"""Simulation-session and button-control routes."""

from typing import Any

from fastapi import APIRouter, Request

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.simulation import run_command, submit
from e87canbus.api.models.simulation import DeviceStatusRequest, StepRequest
from e87canbus.simulation.engine import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    SetDeviceStatus,
    SimulatedDeviceId,
    SimulatedDeviceStatus,
    StepButton,
    snapshot_to_dict,
)

router = APIRouter(prefix="/api", tags=["simulation"])


@router.get("/snapshot")
async def snapshot(request: Request) -> dict[str, Any]:
    return snapshot_to_dict(request.app.state.latest_snapshot, include_trace=True)


@router.post("/reset")
async def reset(request: Request) -> dict[str, Any]:
    result = await submit(request.app, ResetSimulation())
    return snapshot_to_dict(result.snapshot, include_trace=True)


@router.post("/buttons/{button_index}/press")
async def press_button(request: Request, button_index: int) -> dict[str, Any]:
    return await run_command(request.app, PressButton(button_index))


@router.post("/buttons/{button_index}/release")
async def release_button(request: Request, button_index: int) -> dict[str, Any]:
    return await run_command(request.app, ReleaseButton(button_index))


@router.post("/step")
async def step(request: Request, body: StepRequest) -> dict[str, Any]:
    return await run_command(request.app, StepButton(body.button_index))


@router.put("/simulation/devices/{device_id}/status")
async def set_device_status(
    request: Request,
    device_id: str,
    body: DeviceStatusRequest,
) -> dict[str, Any]:
    try:
        validated_device_id = SimulatedDeviceId(device_id)
    except ValueError as exc:
        raise ApiProblem(
            404,
            "device_not_found",
            f"simulated device {device_id!r} does not exist",
        ) from exc
    return await run_command(
        request.app,
        SetDeviceStatus(validated_device_id, SimulatedDeviceStatus(body.status)),
    )
