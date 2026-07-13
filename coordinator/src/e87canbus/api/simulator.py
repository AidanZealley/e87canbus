"""FastAPI app for the browser simulator workbench."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, cast

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from e87canbus.simulation.engine import (
    PressButton,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SimulationCommand,
    SimulationEngine,
    SimulationResult,
    SimulatorSnapshot,
    StepButton,
    snapshot_event,
    snapshot_to_dict,
)

LOGGER = logging.getLogger(__name__)


class StepRequest(BaseModel):
    button_index: int = 0


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._publication_lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        get_snapshot: Callable[[], SimulatorSnapshot],
    ) -> None:
        async with self._publication_lock:
            await websocket.accept()
            await websocket.send_json(snapshot_event(get_snapshot(), include_trace=True))
            self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        async with self._publication_lock:
            disconnected: list[WebSocket] = []
            for websocket in self._connections:
                try:
                    for event in events:
                        await websocket.send_json(event)
                except Exception:
                    LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                    disconnected.append(websocket)
            for websocket in disconnected:
                self.disconnect(websocket)


@dataclass(frozen=True)
class QueuedCommand:
    command: SimulationCommand
    future: asyncio.Future[SimulationResult]


def create_app(
    engine: SimulationEngine | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    simulation = engine or SimulationEngine(clock=clock)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
                    await _submit(app, RunControlTimer(clock()))
                except HTTPException as exc:
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

    app = FastAPI(title="E87 CAN Bus Simulator", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.manager = ConnectionManager()
    app.state.latest_snapshot = simulation.snapshot()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/snapshot")
    async def snapshot() -> dict[str, Any]:
        return snapshot_to_dict(app.state.latest_snapshot, include_trace=True)

    @app.post("/api/reset")
    async def reset() -> dict[str, Any]:
        result = await _submit(app, ResetSimulation())
        return snapshot_to_dict(result.snapshot, include_trace=True)

    @app.post("/api/buttons/{button_index}/press")
    async def press_button(button_index: int) -> dict[str, Any]:
        return await _run_command(app, PressButton(button_index))

    @app.post("/api/buttons/{button_index}/release")
    async def release_button(button_index: int) -> dict[str, Any]:
        return await _run_command(app, ReleaseButton(button_index))

    @app.post("/api/step")
    async def step(request: StepRequest) -> dict[str, Any]:
        return await _run_command(app, StepButton(request.button_index))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await app.state.manager.connect(websocket, lambda: app.state.latest_snapshot)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            app.state.manager.disconnect(websocket)

    return app


async def _run_command(app: FastAPI, command: SimulationCommand) -> dict[str, Any]:
    try:
        result = await _submit(app, command)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return snapshot_to_dict(result.snapshot, include_trace=False)


async def _submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
    future = asyncio.get_running_loop().create_future()
    try:
        app.state.command_queue.put_nowait(QueuedCommand(command, future))
    except asyncio.QueueFull as exc:
        raise HTTPException(status_code=503, detail="simulation command queue is full") from exc
    return cast(SimulationResult, await future)


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 CAN simulator API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the development server when Python source files change.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    uvicorn.run(
        "e87canbus.api.simulator:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload,
        reload_dirs=["coordinator/src"] if args.reload else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
