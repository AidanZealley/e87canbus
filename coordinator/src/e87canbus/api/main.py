"""FastAPI application composition for the simulator workbench."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.api.errors import install_exception_handlers
from e87canbus.api.internal.simulation import create_lifespan
from e87canbus.api.internal.websocket import ConnectionManager
from e87canbus.api.routes import health, simulation, steering, vehicle, websocket
from e87canbus.features.profile_repository import SteeringProfileRepository
from e87canbus.simulation.engine import SimulationEngine

PROFILE_DATABASE_ENVIRONMENT_VARIABLE = "E87CANBUS_PROFILE_DATABASE"
DEFAULT_PROFILE_DATABASE = Path(
    os.environ.get(PROFILE_DATABASE_ENVIRONMENT_VARIABLE, "steering-profiles.sqlite3")
)


def create_app(
    engine: SimulationEngine | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    profile_database_path: str | Path = DEFAULT_PROFILE_DATABASE,
    profile_repository: SteeringProfileRepository | None = None,
) -> FastAPI:
    simulator = engine or SimulationEngine(clock=clock)
    sqlite_repository: SqliteSteeringProfileRepository | None = None
    repository = profile_repository
    if repository is None:
        sqlite_repository = SqliteSteeringProfileRepository(profile_database_path)
        repository = sqlite_repository

    app = FastAPI(
        title="E87 CAN Bus Workbench API",
        lifespan=create_lifespan(simulator, sqlite_repository, clock),
    )
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.state.manager = ConnectionManager(simulator.config.simulation.websocket_send_timeout_s)
    app.state.latest_snapshot = simulator.snapshot()
    app.state.profile_repository = repository

    app.include_router(health.router)
    app.include_router(simulation.router)
    app.include_router(vehicle.router)
    app.include_router(steering.router)
    app.include_router(websocket.router)
    return app


app = create_app()
