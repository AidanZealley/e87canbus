from fastapi import APIRouter, Request

from e87canbus.simulation.api.internal.commands import run_command
from e87canbus.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.simulation.api.models.vehicle import (
    EngineRpmRequest,
    SpeedRequest,
    TemperatureRequest,
)
from e87canbus.simulation.commands import (
    SetVehicleSignal,
    SilenceVehicleSignal,
)
from e87canbus.simulation.signals import VehicleSignal

router = APIRouter(
    prefix="/api/dev/simulation/vehicle",
    tags=["development simulation: vehicle"],
)


@router.put("/speed")
async def set_vehicle_speed(
    request: Request, body: SpeedRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app, SetVehicleSignal(VehicleSignal.SPEED, body.speed_kph)
    )


@router.post("/speed/silence")
async def silence_vehicle_speed(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app, SilenceVehicleSignal(VehicleSignal.SPEED)
    )


@router.put("/rpm")
async def set_engine_rpm(
    request: Request, body: EngineRpmRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app, SetVehicleSignal(VehicleSignal.RPM, body.rpm)
    )


@router.post("/rpm/silence")
async def silence_engine_rpm(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app, SilenceVehicleSignal(VehicleSignal.RPM)
    )


@router.put("/oil-temperature")
async def set_oil_temperature(
    request: Request, body: TemperatureRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetVehicleSignal(VehicleSignal.OIL_TEMPERATURE, body.temperature_c),
    )


@router.post("/oil-temperature/silence")
async def silence_oil_temperature(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app, SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE)
    )


@router.put("/coolant-temperature")
async def set_coolant_temperature(
    request: Request, body: TemperatureRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE, body.temperature_c),
    )


@router.post("/coolant-temperature/silence")
async def silence_coolant_temperature(
    request: Request,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SilenceVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE),
    )
