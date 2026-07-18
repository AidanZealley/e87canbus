"""Development simulation actions backed by the unified controller service."""

from fastapi import FastAPI

from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.simulation.api.models.common import SimulationCommandAcknowledgement
from e87canbus.simulation.commands import SimulationCommand


async def run_command(
    app: FastAPI,
    command: SimulationCommand,
) -> SimulationCommandAcknowledgement:
    await submit_runtime_work(app, command)
    return SimulationCommandAcknowledgement(
        boot_id=app.state.controller_service.boot_id
    )
