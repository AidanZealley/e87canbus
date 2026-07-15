"""Development simulation actions backed by the unified controller service."""

from __future__ import annotations

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.api.models.simulation import SimulationCommandAcknowledgement
from e87canbus.simulation.runtime import SimulationCommand, SimulationResult


async def run_command(
    app: FastAPI,
    command: SimulationCommand,
) -> SimulationCommandAcknowledgement:
    result = await submit_runtime_work(app, command)
    if not isinstance(result, SimulationResult):
        raise ApiProblem(
            503,
            "controller_runtime_error",
            "controller returned an invalid development-action result",
        )
    if result.snapshot.fatal:
        raise ApiProblem(
            503,
            "controller_failed",
            "controller entered a failed state while processing the development action",
        )
    service = app.state.controller_service
    return SimulationCommandAcknowledgement(boot_id=service.boot_id)
