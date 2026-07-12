"""FastAPI app for the browser simulator workbench."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from e87canbus.simulation.controller import SimulatorController, snapshot_event, snapshot_to_dict

LOGGER = logging.getLogger(__name__)


class StepRequest(BaseModel):
    button_index: int = 0


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        disconnected: list[WebSocket] = []
        for websocket in self._connections:
            try:
                for event in events:
                    await websocket.send_json(event)
            except RuntimeError:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


def create_app(controller: SimulatorController | None = None) -> FastAPI:
    app = FastAPI(title="E87 CAN Bus Simulator")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.controller = controller or SimulatorController()
    app.state.manager = ConnectionManager()
    app.state.lock = asyncio.Lock()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/snapshot")
    async def snapshot() -> dict[str, Any]:
        async with app.state.lock:
            return snapshot_to_dict(app.state.controller.snapshot())

    @app.post("/api/reset")
    async def reset() -> dict[str, Any]:
        async with app.state.lock:
            result = app.state.controller.reset()
            events = app.state.controller.last_events
        await app.state.manager.broadcast(events)
        return snapshot_to_dict(result)

    @app.post("/api/buttons/{button_index}/press")
    async def press_button(button_index: int) -> dict[str, Any]:
        return await _run_command(app, "press_button", button_index)

    @app.post("/api/buttons/{button_index}/release")
    async def release_button(button_index: int) -> dict[str, Any]:
        return await _run_command(app, "release_button", button_index)

    @app.post("/api/buttons/{button_index}/toggle")
    async def toggle_button(button_index: int) -> dict[str, Any]:
        return await _run_command(app, "toggle_button", button_index)

    @app.post("/api/step")
    async def step(request: StepRequest) -> dict[str, Any]:
        return await _run_command(app, "step_auto", request.button_index)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await app.state.manager.connect(websocket)
        try:
            async with app.state.lock:
                await websocket.send_json(snapshot_event(app.state.controller.snapshot()))
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            app.state.manager.disconnect(websocket)

    return app


async def _run_command(app: FastAPI, method_name: str, button_index: int) -> dict[str, Any]:
    async with app.state.lock:
        controller: SimulatorController = app.state.controller
        method = getattr(controller, method_name)
        try:
            result = method(button_index)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        events = controller.last_events
    await app.state.manager.broadcast(events)
    return snapshot_to_dict(result)


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 CAN simulator API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    uvicorn.run(
        "e87canbus.api.simulator:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
