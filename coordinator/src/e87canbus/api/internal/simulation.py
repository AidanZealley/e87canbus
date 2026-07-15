"""Development simulation actions backed by the unified controller service."""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI

from e87canbus.api.internal.commands import submit_runtime_work
from e87canbus.simulation.runtime import (
    SimulationCommand,
    SimulationResult,
    snapshot_to_dict,
)


async def run_command(app: FastAPI, command: SimulationCommand) -> dict[str, Any]:
    result = await submit(app, command)
    return snapshot_to_dict(result.snapshot, include_trace=False)


async def submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
    result = await submit_runtime_work(app, command)
    return cast(SimulationResult, result)
