"""Development simulation actions backed by the unified controller service."""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI

from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.api.models.simulation import SimulationCommandAcknowledgement
from e87canbus.simulation.runtime import SimulationCommand, SimulationResult


async def run_command(
    app: FastAPI,
    command: SimulationCommand,
) -> SimulationCommandAcknowledgement:
    await submit(app, command)
    service = app.state.controller_service
    return SimulationCommandAcknowledgement(boot_id=service.boot_id)


async def submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
    result = await submit_runtime_work(app, command)
    return cast(SimulationResult, result)
