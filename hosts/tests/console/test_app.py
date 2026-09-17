from __future__ import annotations

import asyncio
from queue import Empty, Queue

from e87canbus.console.app import create_app
from e87canbus.protocol.can import CanFrame
from fastapi.testclient import TestClient
from starlette.requests import Request


class FakeReceiver:
    def __init__(self) -> None:
        self.frames: Queue[CanFrame] = Queue()
        self.closed = False

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        try:
            return self.frames.get(timeout=timeout_s)
        except Empty:
            return None

    def shutdown(self) -> None:
        self.closed = True


def test_console_lifecycle_starts_and_stops_the_receiver() -> None:
    receiver = FakeReceiver()
    app = create_app(receiver_factory=lambda: receiver)
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "live"}
        assert client.get("/health/ready").status_code == 200
    assert receiver.closed is True


def test_open_failure_keeps_liveness_available_and_readiness_false() -> None:
    def fail_open() -> FakeReceiver:
        raise OSError("kcan missing")

    app = create_app(receiver_factory=fail_open)
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_live_route_is_a_same_origin_uncached_event_stream() -> None:
    app = create_app(receiver_factory=FakeReceiver)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/api/live")

    async def response_metadata() -> tuple[str | None, str | None]:
        response = await route.endpoint(  # type: ignore[union-attr]
            Request({"type": "http", "app": app})
        )
        return response.media_type, response.headers.get("cache-control")

    assert asyncio.run(response_metadata()) == ("text/event-stream", "no-store")
