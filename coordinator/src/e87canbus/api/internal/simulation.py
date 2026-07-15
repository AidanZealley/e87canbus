"""Legacy simulator transport backed by the unified controller service."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future
from typing import Any, cast

from fastapi import FastAPI

from e87canbus.api.errors import ApiProblem
from e87canbus.service import (
    ControllerInboxFull,
    ControllerServiceNotRunning,
)
from e87canbus.simulation.runtime import (
    SimulationCommand,
    SimulationResult,
    SimulationSessionFailed,
    snapshot_to_dict,
)


async def run_command(app: FastAPI, command: SimulationCommand) -> dict[str, Any]:
    try:
        result = await submit(app, command)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    except SimulationSessionFailed as exc:
        raise ApiProblem(409, "simulation_session_failed", str(exc)) from exc
    return snapshot_to_dict(result.snapshot, include_trace=False)


async def submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
    try:
        future: Future[object] = app.state.controller_service.submit(command)
    except ControllerInboxFull as exc:
        raise ApiProblem(
            503,
            "runtime_queue_full",
            "controller runtime inbox is full",
        ) from exc
    except ControllerServiceNotRunning as exc:
        raise ApiProblem(503, "runtime_unavailable", str(exc)) from exc
    result = await asyncio.wrap_future(future)
    return cast(SimulationResult, result)
