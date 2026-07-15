"""Development simulation actions backed by the unified controller service."""

from __future__ import annotations

from fastapi import FastAPI

from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.api.models.simulation import SimulationCommandAcknowledgement
from e87canbus.simulation.runtime import SimulationCommand


async def run_command(
    app: FastAPI,
    command: SimulationCommand,
) -> SimulationCommandAcknowledgement:
    await submit_runtime_work(app, command)
    service = app.state.controller_service
    return SimulationCommandAcknowledgement(boot_id=service.boot_id)
