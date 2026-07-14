"""Simulated vehicle input routes."""

from typing import Any

from fastapi import APIRouter, Request

from e87canbus.api.internal.simulation import run_command
from e87canbus.api.models.simulation import SpeedRequest
from e87canbus.simulation.engine import SetVehicleSpeed, SilenceVehicleSpeed

router = APIRouter(prefix="/api/vehicle", tags=["vehicle"])


@router.post("/speed")
async def set_vehicle_speed(request: Request, body: SpeedRequest) -> dict[str, Any]:
    return await run_command(request.app, SetVehicleSpeed(body.speed_kph))


@router.post("/speed/silence")
async def silence_vehicle_speed(request: Request) -> dict[str, Any]:
    return await run_command(request.app, SilenceVehicleSpeed())
