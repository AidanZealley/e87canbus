"""Coordinator browser live-state stream."""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from e87canbus.api.models.coordinator_live import CoordinatorLiveEvent

router = APIRouter(tags=["live"])


class EventStreamResponse(StreamingResponse, JSONResponse):
    """Stream bytes while letting FastAPI document the JSON record model."""

    media_type = "text/event-stream"


@router.get(
    "/api/live",
    response_model=CoordinatorLiveEvent,
    response_class=EventStreamResponse,
)
async def stream_coordinator_live(request: Request) -> EventStreamResponse:
    # Starlette may drive the body in a child task for ASGI versions before 2.4. The
    # publisher must cancel the outer request so the disconnect listener ends too.
    request_task = asyncio.current_task()
    if request_task is None:
        raise RuntimeError("coordinator SSE route requires an asyncio task")
    return EventStreamResponse(
        request.app.state.live_publisher.events(request_task),
        headers={"Cache-Control": "no-store"},
    )
