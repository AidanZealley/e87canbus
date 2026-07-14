"""FastAPI app for the browser simulator workbench."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, cast

import uvicorn
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.features.profile_repository import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRevisionConflictError,
    SteeringProfileRepository,
    SteeringProfileStorageError,
)
from e87canbus.features.steering import (
    CurveInterpolation,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    StoredSteeringProfile,
    validate_steering_profile_id,
)
from e87canbus.simulation.engine import (
    ActivateCurve,
    PressButton,
    ReleaseButton,
    ResetSimulation,
    RunControlTimer,
    SetVehicleSpeed,
    SilenceVehicleSpeed,
    SimulationCommand,
    SimulationEngine,
    SimulationResult,
    SimulationSessionFailed,
    SimulatorSnapshot,
    StepButton,
    snapshot_event,
    snapshot_to_dict,
)

LOGGER = logging.getLogger(__name__)
PROFILE_DATABASE_ENVIRONMENT_VARIABLE = "E87CANBUS_PROFILE_DATABASE"
DEFAULT_PROFILE_DATABASE = Path(
    os.environ.get(PROFILE_DATABASE_ENVIRONMENT_VARIABLE, "steering-profiles.sqlite3")
)
T = TypeVar("T")


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SteeringCurvePointRequest(StrictRequest):
    speed_deci_kph: int
    assistance_per_mille: int


class SteeringCurveDefinitionRequest(StrictRequest):
    schema_version: int
    interpolation: str
    points: list[SteeringCurvePointRequest]


class CreateProfileRequest(StrictRequest):
    name: str
    definition: SteeringCurveDefinitionRequest


class UpdateProfileRequest(CreateProfileRequest):
    expected_revision: int = Field(ge=1)


class ActivateCurveRequest(StrictRequest):
    definition: SteeringCurveDefinitionRequest
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = Field(default=None, ge=1)


class ApiProblem(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        current_revision: int | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.current_revision = current_revision


def _definition_from_request(
    request: SteeringCurveDefinitionRequest,
) -> SteeringCurveDefinition:
    try:
        interpolation = CurveInterpolation(request.interpolation)
        return SteeringCurveDefinition(
            schema_version=request.schema_version,
            interpolation=interpolation,
            points=tuple(
                SteeringCurvePoint(point.speed_deci_kph, point.assistance_per_mille)
                for point in request.points
            ),
        )
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def _definition_to_dict(definition: SteeringCurveDefinition) -> dict[str, Any]:
    return {
        "schema_version": definition.schema_version,
        "interpolation": definition.interpolation.value,
        "points": [
            {
                "speed_deci_kph": point.speed_deci_kph,
                "assistance_per_mille": point.assistance_per_mille,
            }
            for point in definition.points
        ],
    }


def _profile_to_dict(profile: StoredSteeringProfile) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "name": profile.name,
        "revision": profile.revision,
        "definition": _definition_to_dict(profile.definition),
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _curve_state_to_dict(snapshot: SimulatorSnapshot) -> dict[str, Any]:
    active = snapshot.application.active_steering_curve
    return {
        "definition": _definition_to_dict(active.definition),
        "fingerprint": active.fingerprint,
        "activation_revision": active.activation_revision,
        "status": snapshot.application.steering_curve_activation_status.value,
        "saved_profile_id": active.saved_profile_id,
        "saved_profile_revision": active.saved_profile_revision,
    }


class StepRequest(BaseModel):
    button_index: int = 0


class SpeedRequest(BaseModel):
    speed_kph: float


class ConnectionManager:
    def __init__(self, send_timeout_s: float) -> None:
        self._connections: set[WebSocket] = set()
        self._publication_lock = asyncio.Lock()
        self._send_timeout_s = send_timeout_s

    async def connect(
        self,
        websocket: WebSocket,
        get_snapshot: Callable[[], SimulatorSnapshot],
    ) -> bool:
        async with self._publication_lock:
            await websocket.accept()
            try:
                await self._send_events(
                    websocket,
                    (snapshot_event(get_snapshot(), include_trace=True),),
                )
            except Exception:
                LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                return False
            self._connections.add(websocket)
            return True

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def send(self, websocket: WebSocket, event: dict[str, Any]) -> bool:
        async with self._publication_lock:
            try:
                await self._send_events(websocket, (event,))
            except Exception:
                LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                self.disconnect(websocket)
                return False
            return True

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        async with self._publication_lock:
            disconnected: list[WebSocket] = []
            for websocket in tuple(self._connections):
                try:
                    await self._send_events(websocket, events)
                except Exception:
                    LOGGER.warning("removing failed simulator WebSocket", exc_info=True)
                    disconnected.append(websocket)
            for websocket in disconnected:
                self.disconnect(websocket)

    async def _send_events(
        self,
        websocket: WebSocket,
        events: Sequence[dict[str, Any]],
    ) -> None:
        async with asyncio.timeout(self._send_timeout_s):
            for event in events:
                await websocket.send_json(event)


@dataclass(frozen=True)
class QueuedCommand:
    command: SimulationCommand
    future: asyncio.Future[SimulationResult]


def create_app(
    engine: SimulationEngine | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    profile_database_path: str | Path = DEFAULT_PROFILE_DATABASE,
    profile_repository: SteeringProfileRepository | None = None,
) -> FastAPI:
    simulation = engine or SimulationEngine(clock=clock)
    sqlite_repository: SqliteSteeringProfileRepository | None = None
    repository = profile_repository
    if repository is None:
        sqlite_repository = SqliteSteeringProfileRepository(profile_database_path)
        repository = sqlite_repository

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
                    await _submit(app, RunControlTimer(clock()))
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

    app = FastAPI(title="E87 CAN Bus Simulator", lifespan=lifespan)

    @app.exception_handler(ApiProblem)
    async def api_problem_handler(_request: Request, exc: ApiProblem) -> JSONResponse:
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.current_revision is not None:
            error["current_revision"] = exc.current_revision
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        issues = [
            {"location": list(issue["loc"]), "message": issue["msg"], "type": issue["type"]}
            for issue in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request validation failed",
                    "issues": issues,
                }
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.state.manager = ConnectionManager(
        simulation.config.simulation.websocket_send_timeout_s
    )
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

    @app.post("/api/vehicle/speed")
    async def set_vehicle_speed(request: SpeedRequest) -> dict[str, Any]:
        return await _run_command(app, SetVehicleSpeed(request.speed_kph))

    @app.post("/api/vehicle/speed/silence")
    async def silence_vehicle_speed() -> dict[str, Any]:
        return await _run_command(app, SilenceVehicleSpeed())

    @app.get("/api/steering/profiles")
    async def list_steering_profiles() -> dict[str, Any]:
        profiles = await _repository_operation(repository.list_profiles)
        return {"profiles": [_profile_to_dict(profile) for profile in profiles]}

    @app.post("/api/steering/profiles", status_code=201)
    async def create_steering_profile(request: CreateProfileRequest) -> dict[str, Any]:
        definition = _definition_from_request(request.definition)
        profile = await _repository_operation(
            lambda: repository.create_profile(request.name, definition)
        )
        await _publish_profile_catalog_changed(app)
        return _profile_to_dict(profile)

    @app.get("/api/steering/profiles/{profile_id}")
    async def get_steering_profile(profile_id: str) -> dict[str, Any]:
        _validate_profile_id(profile_id)
        profile = await _repository_operation(lambda: repository.get_profile(profile_id))
        if profile is None:
            raise ApiProblem(404, "profile_not_found", f"steering profile not found: {profile_id}")
        return _profile_to_dict(profile)

    @app.put("/api/steering/profiles/{profile_id}")
    async def update_steering_profile(
        profile_id: str, request: UpdateProfileRequest
    ) -> dict[str, Any]:
        _validate_profile_id(profile_id)
        definition = _definition_from_request(request.definition)
        profile = await _repository_operation(
            lambda: repository.update_profile(
                profile_id,
                request.expected_revision,
                request.name,
                definition,
            )
        )
        await _publish_profile_catalog_changed(app)
        return _profile_to_dict(profile)

    @app.delete("/api/steering/profiles/{profile_id}", status_code=204)
    async def delete_steering_profile(
        profile_id: str,
        expected_revision: int = Query(ge=1),
    ) -> None:
        _validate_profile_id(profile_id)
        await _repository_operation(
            lambda: repository.delete_profile(profile_id, expected_revision)
        )
        await _publish_profile_catalog_changed(app)

    @app.get("/api/steering/curve-state")
    async def steering_curve_state() -> dict[str, Any]:
        return _curve_state_to_dict(app.state.latest_snapshot)

    @app.post("/api/steering/curve-state/activate")
    async def activate_steering_curve(request: ActivateCurveRequest) -> dict[str, Any]:
        definition = _definition_from_request(request.definition)
        saved_profile_id = request.saved_profile_id
        saved_profile_revision = request.saved_profile_revision
        if (saved_profile_id is None) != (saved_profile_revision is None):
            raise ApiProblem(
                422,
                "validation_error",
                "saved_profile_id and saved_profile_revision must be supplied together",
            )
        if saved_profile_id is not None:
            _validate_profile_id(saved_profile_id, field_name="saved_profile_id")
            saved = await _repository_operation(
                lambda: repository.get_profile(saved_profile_id)
            )
            current_revision = None if saved is None else saved.revision
            if (
                saved is None
                or saved.revision != saved_profile_revision
                or saved.definition != definition
            ):
                raise ApiProblem(
                    409,
                    "saved_provenance_mismatch",
                    "claimed saved profile provenance does not match the committed definition",
                    current_revision=current_revision,
                )
        try:
            result = await _submit(
                app,
                ActivateCurve(definition, saved_profile_id, saved_profile_revision),
            )
        except ValueError as exc:
            raise ApiProblem(422, "validation_error", str(exc)) from exc
        except SimulationSessionFailed as exc:
            raise ApiProblem(409, "simulation_session_failed", str(exc)) from exc
        if result.snapshot.fatal:
            raise ApiProblem(
                503,
                "activation_effect_failed",
                "curve activation committed but its immediate runtime effect failed",
            )
        return _curve_state_to_dict(result.snapshot)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        connected = await app.state.manager.connect(
            websocket, lambda: app.state.latest_snapshot
        )
        if not connected:
            return
        try:
            while True:
                message = await websocket.receive_text()
                if message == "ping" and not await app.state.manager.send(
                    websocket, {"type": "heartbeat"}
                ):
                    return
        except WebSocketDisconnect:
            app.state.manager.disconnect(websocket)

    return app


async def _run_command(app: FastAPI, command: SimulationCommand) -> dict[str, Any]:
    try:
        result = await _submit(app, command)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc
    except SimulationSessionFailed as exc:
        raise ApiProblem(409, "simulation_session_failed", str(exc)) from exc
    return snapshot_to_dict(result.snapshot, include_trace=False)


async def _submit(app: FastAPI, command: SimulationCommand) -> SimulationResult:
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


async def _repository_operation(operation: Callable[[], T]) -> T:
    try:
        return await asyncio.to_thread(operation)
    except ProfileRevisionConflictError as exc:
        raise ApiProblem(
            409,
            "profile_revision_conflict",
            str(exc),
            current_revision=exc.actual_revision,
        ) from exc
    except ProfileNameConflictError as exc:
        raise ApiProblem(409, "profile_name_conflict", str(exc)) from exc
    except ProfileNotFoundError as exc:
        raise ApiProblem(404, "profile_not_found", str(exc)) from exc
    except SteeringProfileStorageError as exc:
        raise ApiProblem(503, "profile_storage_error", str(exc)) from exc
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


def _validate_profile_id(profile_id: str, *, field_name: str = "profile_id") -> None:
    try:
        validate_steering_profile_id(profile_id, field_name=field_name)
    except ValueError as exc:
        raise ApiProblem(422, "validation_error", str(exc)) from exc


async def _publish_profile_catalog_changed(app: FastAPI) -> None:
    await app.state.manager.broadcast(({"type": "steering_profile_catalog_changed"},))


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the E87 CAN simulator API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--profile-database",
        type=Path,
        default=DEFAULT_PROFILE_DATABASE,
        help="SQLite steering-profile database path.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Restart the development server when Python source files change.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    global app

    args = build_parser().parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    os.environ[PROFILE_DATABASE_ENVIRONMENT_VARIABLE] = str(args.profile_database)
    app = create_app(profile_database_path=args.profile_database)
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
