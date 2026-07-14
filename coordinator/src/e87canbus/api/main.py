"""FastAPI application composition for the simulator workbench."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.adapters.sqlite_settings import SqliteApplicationSettingsRepository
from e87canbus.api.errors import install_exception_handlers
from e87canbus.api.internal.simulation import create_lifespan
from e87canbus.api.internal.websocket import ConnectionManager
from e87canbus.api.routes import health, settings, simulation, steering, vehicle, websocket
from e87canbus.features.profile_repository import SteeringProfileRepository
from e87canbus.features.settings_repository import ApplicationSettingsRepository
from e87canbus.simulation.engine import SimulationEngine

PROFILE_DATABASE_ENVIRONMENT_VARIABLE = "E87CANBUS_PROFILE_DATABASE"
DEFAULT_PROFILE_DATABASE = Path(
    os.environ.get(PROFILE_DATABASE_ENVIRONMENT_VARIABLE, "steering-profiles.sqlite3")
)
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


def create_app(
    engine: SimulationEngine | None = None,
    *,
    clock: Callable[[], float] = time.monotonic,
    profile_database_path: str | Path = DEFAULT_PROFILE_DATABASE,
    profile_repository: SteeringProfileRepository | None = None,
    settings_repository: ApplicationSettingsRepository | None = None,
    cors_origins: Sequence[str] = DEFAULT_CORS_ORIGINS,
) -> FastAPI:
    simulator = engine or SimulationEngine(clock=clock)
    database = (
        SqliteApplicationDatabase(profile_database_path)
        if profile_repository is None or settings_repository is None
        else None
    )
    if profile_repository is None:
        assert database is not None
        profile_repository = SqliteSteeringProfileRepository(database)
    if settings_repository is None:
        assert database is not None
        settings_repository = SqliteApplicationSettingsRepository(database)

    app = FastAPI(
        title="E87 CAN Bus Workbench API",
        lifespan=create_lifespan(simulator, database, clock),
    )
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.state.manager = ConnectionManager(simulator.config.simulation.websocket_send_timeout_s)
    app.state.latest_snapshot = simulator.snapshot()
    app.state.profile_repository = profile_repository
    app.state.settings_repository = settings_repository

    app.include_router(health.router)
    app.include_router(simulation.router)
    app.include_router(vehicle.router)
    app.include_router(steering.router)
    app.include_router(settings.router)
    app.include_router(websocket.router)
    return app


app = create_app()
