from fastapi import APIRouter, Request

from e87canbus.simulation.api.internal.commands import run_command
from e87canbus.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.simulation.commands import ResetSimulation

router = APIRouter(
    prefix="/api/dev/simulation",
    tags=["development simulation: session"],
)


@router.post("/reset")
async def reset(request: Request) -> SimulationCommandAcknowledgement:
    return await run_command(request.app, ResetSimulation())
