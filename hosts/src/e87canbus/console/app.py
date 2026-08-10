"""FastAPI composition for the local console service and built frontend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import socketio  # type: ignore[import-untyped]
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.adapters.socketio_server import BoundedSocketIoServer
from e87canbus.adapters.web import SpaStaticFiles
from e87canbus.console.live import ConsoleLivePublisher, install_socket_handlers
from e87canbus.console.service import ConsoleCanService, ManagedCanReceiver

CONSOLE_SOCKET_PATH = "/console/socket.io"


def create_app(
    *,
    receiver_factory: Callable[[], ManagedCanReceiver] | None = None,
    frontend_directory: str | Path | None = None,
) -> FastAPI:
    service = ConsoleCanService(receiver_factory or (lambda: SocketCanBus("kcan")))
    sio = BoundedSocketIoServer(
        async_mode="asgi",
        outbound_queue_capacity=8,
    )
    publisher = ConsoleLivePublisher(sio, service)
    install_socket_handlers(sio, publisher)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await publisher.start()
        service.start(publisher.offer)
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(service.stop)
            finally:
                await publisher.stop()

    app = FastAPI(title="E87 Console", lifespan=lifespan)
    app.state.console_service = service
    app.state.socketio = sio
    app.state.live_publisher = publisher

    @app.get("/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/health/ready")
    async def readiness() -> JSONResponse:
        snapshot = service.snapshot()
        ready = service.ready
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "boot_id": snapshot.boot_id,
            },
        )

    static_app = (
        SpaStaticFiles(directory=frontend_directory, html=True)
        if frontend_directory is not None
        else None
    )
    app.mount(
        "/",
        socketio.ASGIApp(
            sio,
            other_asgi_app=static_app,
            socketio_path=CONSOLE_SOCKET_PATH.lstrip("/"),
        ),
        name="socket.io",
    )
    return app


app = create_app()
