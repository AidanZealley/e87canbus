from fastapi import APIRouter, Request

from e87canbus.api.errors import api_problem_responses
from e87canbus.runners.simulation.api.internal.commands import run_command
from e87canbus.runners.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.runners.simulation.api.models.vehicle import (
    EngineRpmRequest,
    SpeedRequest,
    TemperatureRequest,
)
from e87canbus.runners.simulation.commands import (
    SetVehicleSignal,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.signals import VehicleSignal

router = APIRouter(
    prefix="/api/dev/simulation/vehicle",
    tags=["development simulation: vehicle"],
)


@router.put(
    "/speed",
    operation_id="setVehicleSpeed",
    responses=api_problem_responses(409, 422, 503),
)
async def set_vehicle_speed(
    request: Request, body: SpeedRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetVehicleSignal(VehicleSignal.SPEED, body.speed_kph))


@router.post(
    "/speed/silence",
    operation_id="silenceVehicleSpeed",
    responses=api_problem_responses(409, 422, 503),
)
async def silence_vehicle_speed(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceVehicleSignal(VehicleSignal.SPEED))


@router.put(
    "/rpm",
    operation_id="setEngineRpm",
    responses=api_problem_responses(409, 422, 503),
)
async def set_engine_rpm(
    request: Request, body: EngineRpmRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetVehicleSignal(VehicleSignal.RPM, body.rpm))


@router.post(
    "/rpm/silence",
    operation_id="silenceEngineRpm",
    responses=api_problem_responses(409, 422, 503),
)
async def silence_engine_rpm(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceVehicleSignal(VehicleSignal.RPM))


@router.put(
    "/oil-temperature",
    operation_id="setOilTemperature",
    responses=api_problem_responses(409, 422, 503),
)
async def set_oil_temperature(
    request: Request, body: TemperatureRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetVehicleSignal(VehicleSignal.OIL_TEMPERATURE, body.temperature_c),
    )


@router.post(
    "/oil-temperature/silence",
    operation_id="silenceOilTemperature",
    responses=api_problem_responses(409, 422, 503),
)
async def silence_oil_temperature(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE))


@router.put(
    "/coolant-temperature",
    operation_id="setCoolantTemperature",
    responses=api_problem_responses(409, 422, 503),
)
async def set_coolant_temperature(
    request: Request, body: TemperatureRequest
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SetVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE, body.temperature_c),
    )


@router.post(
    "/coolant-temperature/silence",
    operation_id="silenceCoolantTemperature",
    responses=api_problem_responses(409, 422, 503),
)
async def silence_coolant_temperature(
    request: Request,
) -> SimulationCommandAcknowledgement:
    return await run_command(
        request.app,
        SilenceVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE),
    )
