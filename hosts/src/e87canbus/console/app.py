"""FastAPI composition for the local console service and built frontend."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.adapters.web import SpaStaticFiles
from e87canbus.console.models import ConsoleSnapshotEvent
from e87canbus.console.service import (
    ConsoleCanService,
    ManagedCanReceiver,
)
from e87canbus.console.sse import ConsoleSsePublisher


class EventStreamResponse(StreamingResponse, JSONResponse):
    """Stream bytes while letting FastAPI document the JSON record model."""

    media_type = "text/event-stream"


def create_app(
    *,
    receiver_factory: Callable[[], ManagedCanReceiver] | None = None,
    frontend_directory: str | Path | None = None,
) -> FastAPI:
    service = ConsoleCanService(receiver_factory or (lambda: SocketCanBus("kcan")))
    sse_publisher = ConsoleSsePublisher(service)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await sse_publisher.start()
        service.start(sse_publisher.offer)
        try:
            yield
        finally:
            try:
                await asyncio.to_thread(service.stop)
            finally:
                await sse_publisher.stop()

    app = FastAPI(title="E87 Console", lifespan=lifespan)
    app.state.console_service = service
    app.state.sse_publisher = sse_publisher

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

    @app.get(
        "/api/live",
        response_model=ConsoleSnapshotEvent,
        response_class=EventStreamResponse,
    )
    async def stream_console_live(request: Request) -> EventStreamResponse:
        # Starlette may drive the body in a child task for ASGI versions before 2.4.
        # Cancel the outer request to release both tasks when a subscriber is too slow.
        request_task = asyncio.current_task()
        if request_task is None:
            raise RuntimeError("console SSE route requires an asyncio task")
        return EventStreamResponse(
            request.app.state.sse_publisher.events(request_task),
            headers={"Cache-Control": "no-store"},
        )

    if frontend_directory is not None:
        app.mount(
            "/",
            SpaStaticFiles(directory=frontend_directory, html=True),
            name="frontend",
        )
    return app


app = create_app()
