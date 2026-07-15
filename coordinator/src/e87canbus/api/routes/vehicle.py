"""Simulated vehicle input routes."""

from typing import Any

from fastapi import APIRouter, Request

from e87canbus.api.internal.simulation import run_command
from e87canbus.api.models.simulation import EngineRpmRequest, SpeedRequest, TemperatureRequest
from e87canbus.simulation.runtime import (
    SetCoolantTemperature,
    SetEngineRpm,
    SetOilTemperature,
    SetVehicleSpeed,
    SilenceCoolantTemperature,
    SilenceEngineRpm,
    SilenceOilTemperature,
    SilenceVehicleSpeed,
)

router = APIRouter(prefix="/api/vehicle", tags=["vehicle"])


@router.post("/speed")
async def set_vehicle_speed(request: Request, body: SpeedRequest) -> dict[str, Any]:
    return await run_command(request.app, SetVehicleSpeed(body.speed_kph))


@router.post("/speed/silence")
async def silence_vehicle_speed(request: Request) -> dict[str, Any]:
    return await run_command(request.app, SilenceVehicleSpeed())


@router.post("/rpm")
async def set_engine_rpm(request: Request, body: EngineRpmRequest) -> dict[str, Any]:
    return await run_command(request.app, SetEngineRpm(body.rpm))


@router.post("/rpm/silence")
async def silence_engine_rpm(request: Request) -> dict[str, Any]:
    return await run_command(request.app, SilenceEngineRpm())


@router.post("/oil-temperature")
async def set_oil_temperature(
    request: Request,
    body: TemperatureRequest,
) -> dict[str, Any]:
    return await run_command(request.app, SetOilTemperature(body.temperature_c))


@router.post("/oil-temperature/silence")
async def silence_oil_temperature(request: Request) -> dict[str, Any]:
    return await run_command(request.app, SilenceOilTemperature())


@router.post("/coolant-temperature")
async def set_coolant_temperature(
    request: Request,
    body: TemperatureRequest,
) -> dict[str, Any]:
    return await run_command(request.app, SetCoolantTemperature(body.temperature_c))


@router.post("/coolant-temperature/silence")
async def silence_coolant_temperature(request: Request) -> dict[str, Any]:
    return await run_command(request.app, SilenceCoolantTemperature())
