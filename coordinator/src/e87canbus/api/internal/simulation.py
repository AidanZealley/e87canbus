"""Simulation command execution and application lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, cast

from fastapi import FastAPI

from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.api.errors import ApiProblem
from e87canbus.simulation.engine import (
    RunControlTimer,
    SimulationCommand,
    SimulationEngine,
    SimulationResult,
    SimulationSessionFailed,
    snapshot_to_dict,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueuedCommand:
    command: SimulationCommand
    future: asyncio.Future[SimulationResult]


def create_lifespan(
    simulation: SimulationEngine,
    sqlite_repository: SqliteSteeringProfileRepository | None,
    clock: Callable[[], float],
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if sqlite_repository is not None:
            await asyncio.to_thread(sqlite_repository.initialize)
        queue: asyncio.Queue[QueuedCommand] = asyncio.Queue(
            maxsize=simulation.config.simulation.command_queue_capacity
        )
        app.state.command_queue = queue

        async def own_engine() -> None:
            while True:
                queued = await queue.get()
                try:
                    result = simulation.execute(queued.command)
                    app.state.latest_snapshot = result.snapshot
                    if result.events:
                        await app.state.manager.broadcast(result.events)
                except Exception as exc:
                    if not queued.future.done():
                        queued.future.set_exception(exc)
                else:
                    if not queued.future.done():
                        queued.future.set_result(result)
                finally:
                    queue.task_done()

        async def run_timer() -> None:
            while True:
                await asyncio.sleep(simulation.config.tick_interval_s)
                try:
                    await submit(app, RunControlTimer(clock()))
                except SimulationSessionFailed:
                    continue
                except ApiProblem as exc:
                    if exc.status_code != 503:
                        raise
                    LOGGER.warning("skipped control timer because simulation queue is full")

        owner_task = asyncio.create_task(own_engine())
        timer_task = asyncio.create_task(run_timer())
        try:
            yield
        finally:
            timer_task.cancel()
            with suppress(asyncio.CancelledError):
                await timer_task
            owner_task.cancel()
            with suppress(asyncio.CancelledError):
                await owner_task

    return lifespan


async def run_command(app: FastAPI, command: SimulationCommand) -> dict[str, Any]:
    try:
        result = await submit(app, command)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    except SimulationSessionFailed as exc:
        raise ApiProblem(409, "simulation_session_failed", str(exc)) from exc
    return snapshot_to_dict(result.snapshot, include_trace=False)


async def submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
    future = asyncio.get_running_loop().create_future()
    try:
        app.state.command_queue.put_nowait(QueuedCommand(command, future))
    except asyncio.QueueFull as exc:
        raise ApiProblem(
            503,
            "runtime_queue_full",
            "simulation command queue is full",
        ) from exc
    return cast(SimulationResult, await future)
