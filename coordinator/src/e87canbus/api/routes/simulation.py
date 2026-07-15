"""Development-only simulation adapter actions."""

from fastapi import APIRouter, Request

from e87canbus.api.internal.simulation import run_command
from e87canbus.api.models.simulation import (
    EngineRpmRequest,
    SimulationCommandAcknowledgement,
    SpeedRequest,
    TemperatureRequest,
)
from e87canbus.simulation.runtime import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    SetCoolantTemperature,
    SetEngineRpm,
    SetOilTemperature,
    SetVehicleSpeed,
    SilenceCoolantTemperature,
    SilenceEngineRpm,
    SilenceOilTemperature,
    SilenceVehicleSpeed,
)

router = APIRouter(prefix="/api/dev/simulation", tags=["development simulation"])


@router.post("/reset")
async def reset(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, ResetSimulation())


@router.post("/devices/button-pad/buttons/{button_index}/press")
async def press_button(
    request: Request,
    button_index: int,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, PressButton(button_index))


@router.post("/devices/button-pad/buttons/{button_index}/release")
async def release_button(
    request: Request,
    button_index: int,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, ReleaseButton(button_index))


@router.put("/vehicle/speed")
async def set_vehicle_speed(
    request: Request,
    body: SpeedRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetVehicleSpeed(body.speed_kph))


@router.post("/vehicle/speed/silence")
async def silence_vehicle_speed(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceVehicleSpeed())


@router.put("/vehicle/rpm")
async def set_engine_rpm(
    request: Request,
    body: EngineRpmRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetEngineRpm(body.rpm))


@router.post("/vehicle/rpm/silence")
async def silence_engine_rpm(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceEngineRpm())


@router.put("/vehicle/oil-temperature")
async def set_oil_temperature(
    request: Request,
    body: TemperatureRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetOilTemperature(body.temperature_c))


@router.post("/vehicle/oil-temperature/silence")
async def silence_oil_temperature(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceOilTemperature())


@router.put("/vehicle/coolant-temperature")
async def set_coolant_temperature(
    request: Request,
    body: TemperatureRequest,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SetCoolantTemperature(body.temperature_c))


@router.post("/vehicle/coolant-temperature/silence")
async def silence_coolant_temperature(
    request: Request,
) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, SilenceCoolantTemperature())
