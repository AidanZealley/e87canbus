"""FastAPI composition for the unified live or simulated controller."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHttpException
from starlette.responses import Response
from starlette.types import Scope

from e87canbus.adapters.sqlite_database import SqliteApplicationDatabase
from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.adapters.sqlite_settings import SqliteApplicationSettingsRepository
from e87canbus.api.errors import install_exception_handlers
from e87canbus.api.internal.lifecycle import create_lifespan
from e87canbus.api.internal.live import LiveStatePublisher, install_socket_handlers
from e87canbus.api.internal.socketio_server import BoundedSocketIoServer
from e87canbus.api.routes import commands, health, settings, simulation, steering
from e87canbus.composition import CompositionSelection, build_controller_service
from e87canbus.config import AppConfig
from e87canbus.features.profile_repository import SteeringProfileRepository
from e87canbus.features.settings_repository import ApplicationSettingsRepository
from e87canbus.service import ControllerMode, ControllerService

PROFILE_DATABASE_ENVIRONMENT_VARIABLE = "E87CANBUS_PROFILE_DATABASE"
CONTROLLER_MODE_ENVIRONMENT_VARIABLE = "E87CANBUS_MODE"
DEFAULT_PROFILE_DATABASE = Path(
    os.environ.get(PROFILE_DATABASE_ENVIRONMENT_VARIABLE, "steering-profiles.sqlite3")
)
DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)


class SpaStaticFiles(StaticFiles):
    """Serve the built SPA entry for client routes while preserving asset 404s."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        server_prefixes = ("api", "health", "socket.io", "ws")
        first_segment = path.split("/", maxsplit=1)[0]
        fallback = (
            first_segment not in server_prefixes
            and first_segment != "assets"
            and PurePosixPath(path).suffix == ""
        )
        try:
            response = await super().get_response(path, scope)
        except StarletteHttpException as exc:
            if exc.status_code != 404 or not fallback:
                raise
            return await super().get_response("index.html", scope)
        if response.status_code == 404 and fallback:
            return await super().get_response("index.html", scope)
        return response


def socket_origin_policy(
    development_origins: Sequence[str],
) -> Callable[[str | None, dict[str, str]], bool]:
    allowed_development = frozenset(development_origins)

    def is_allowed(origin: str | None, environ: dict[str, str]) -> bool:
        if origin is None:
            return True
        scheme = environ.get("HTTP_X_FORWARDED_PROTO", environ.get("wsgi.url_scheme", "http"))
        host = environ.get("HTTP_X_FORWARDED_HOST", environ.get("HTTP_HOST", ""))
        forwarded_scheme = scheme.split(",", maxsplit=1)[0].strip()
        forwarded_host = host.split(",", maxsplit=1)[0].strip()
        same_origin = f"{forwarded_scheme}://{forwarded_host}"
        return origin == same_origin or origin in allowed_development

    return is_allowed


def create_app(
    *,
    controller_service: ControllerService | None = None,
    mode: ControllerMode = ControllerMode.SIMULATED,
    config: AppConfig | None = None,
    selection: CompositionSelection | None = None,
    clock: Callable[[], float] = time.monotonic,
    profile_database_path: str | Path = DEFAULT_PROFILE_DATABASE,
    profile_repository: SteeringProfileRepository | None = None,
    settings_repository: ApplicationSettingsRepository | None = None,
    cors_origins: Sequence[str] | None = None,
    frontend_directory: str | Path | None = None,
) -> FastAPI:
    if controller_service is not None and (config is not None or selection is not None):
        raise ValueError("inject either controller_service or composition configuration, not both")
    service = controller_service or build_controller_service(
        mode,
        config=config,
        selection=selection,
        clock=clock,
    )
    if service.mode is not mode:
        raise ValueError(
            f"controller service mode {service.mode.value} does not match API mode {mode.value}"
        )
    selected_cors_origins = (
        tuple(cors_origins)
        if cors_origins is not None
        else (DEFAULT_CORS_ORIGINS if mode is ControllerMode.SIMULATED else ())
    )
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

    sio = BoundedSocketIoServer(
        async_mode="asgi",
        cors_allowed_origins=socket_origin_policy(selected_cors_origins),
        outbound_queue_capacity=service.config.live_publication.client_queue_capacity,
    )
    publisher = LiveStatePublisher(sio, service, service.config)
    install_socket_handlers(sio, publisher)

    app = FastAPI(
        title="E87 CAN Bus Controller API",
        lifespan=create_lifespan(service, database, publisher),
    )
    install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(selected_cors_origins),
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
    )

    app.state.controller_service = service
    app.state.controller_mode = mode
    app.state.socketio = sio
    app.state.live_publisher = publisher
    app.state.profile_repository = profile_repository
    app.state.settings_repository = settings_repository
    app.state.monotonic_clock = clock

    app.include_router(health.router)
    app.include_router(settings.router)
    app.include_router(steering.router)
    app.include_router(commands.router)
    if mode is ControllerMode.SIMULATED:
        app.include_router(simulation.router)
    static_app = (
        SpaStaticFiles(directory=frontend_directory, html=True)
        if frontend_directory is not None
        else None
    )
    app.mount("/", socketio.ASGIApp(sio, other_asgi_app=static_app), name="socket.io")
    return app


app = create_app(
    mode=ControllerMode(
        os.environ.get(CONTROLLER_MODE_ENVIRONMENT_VARIABLE, ControllerMode.SIMULATED)
    )
)
