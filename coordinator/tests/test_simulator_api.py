from collections.abc import Sequence
from dataclasses import replace
from threading import Event
from typing import Any, cast

import pytest
from e87canbus.api.simulator import ConnectionManager, create_app
from e87canbus.config import CanNetwork, default_config
from e87canbus.protocol.can import CanFrame
from e87canbus.simulation.controller import SimulatorController
from fastapi import WebSocket
from fastapi.testclient import TestClient


def make_client() -> TestClient:
    return TestClient(create_app(SimulatorController()))


class TickRecordingController(SimulatorController):
    def __init__(self, ticked: Event) -> None:
        config = replace(default_config(), tick_interval_s=0.001)
        super().__init__(config=config)
        self._ticked = ticked

    def tick(self):
        snapshot = super().tick()
        self._ticked.set()
        return snapshot


class RecordingManager:
    def __init__(self) -> None:
        self.broadcasts: list[Sequence[dict[str, Any]]] = []

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        self.broadcasts.append(events)


class FakeWebSocket:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, event: dict[str, Any]) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(event)


def test_health() -> None:
    client = make_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_browser_cors_preflight() -> None:
    client = make_client()

    response = client.options(
        "/api/buttons/0/press",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_snapshot() -> None:
    client = make_client()

    response = client.get("/api/snapshot")

    assert response.status_code == 200
    assert response.json()["trace"] == []
    assert response.json()["application"]["steering_mode"] == "auto"
    assert response.json()["application"]["speed_valid"] is False
    assert response.json()["led_colours"] == {"0": 3, "3": 0}
    assert response.json()["networks"] == [
        {
            "id": "kcan",
            "label": "K-CAN",
            "interface": "can0",
            "bitrate": 100000,
            "connected": True,
            "nodes": ["pi", "simulated-car", "neotrellis", "steering-controller"],
        },
        {
            "id": "ptcan",
            "label": "PT-CAN",
            "interface": "can1",
            "bitrate": 500000,
            "connected": True,
            "nodes": ["pi", "simulated-car"],
        },
        {
            "id": "fcan",
            "label": "F-CAN",
            "interface": "can2",
            "bitrate": 500000,
            "connected": True,
            "nodes": ["pi", "simulated-car"],
        },
    ]


def test_reset() -> None:
    client = make_client()
    client.post("/api/buttons/0/press")

    response = client.post("/api/reset")

    assert response.status_code == 200
    assert response.json()["trace"] == []
    assert response.json()["application"]["steering_mode"] == "auto"
    assert response.json()["led_colours"] == {"0": 3, "3": 0}


def test_press_button() -> None:
    client = make_client()

    response = client.post("/api/buttons/0/press")

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == "manual"
    assert response.json()["led_colours"] == {"0": 4, "3": 0}
    assert "trace" not in response.json()


def test_release_button() -> None:
    client = make_client()
    client.post("/api/buttons/0/press")

    response = client.post("/api/buttons/0/release")

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == "manual"
    assert response.json()["led_colours"] == {"0": 4, "3": 0}
    assert "trace" not in response.json()


def test_step() -> None:
    client = make_client()

    response = client.post("/api/step", json={"button_index": 0})

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == "manual"
    assert "trace" not in response.json()


def test_invalid_button_index_returns_validation_error() -> None:
    client = make_client()

    response = client.post("/api/buttons/16/press")

    assert response.status_code == 422
    assert "button_index" in response.json()["detail"]


def test_websocket_receives_initial_snapshot() -> None:
    client = make_client()

    with client.websocket_connect("/ws") as websocket:
        event = websocket.receive_json()

    assert event["type"] == "snapshot"
    assert event["snapshot"]["trace"] == []


def test_websocket_frame_events_include_network_metadata() -> None:
    client = make_client()

    with client.websocket_connect("/ws") as websocket:
        websocket.receive_json()
        response = client.post("/api/buttons/0/press")
        assert response.status_code == 200
        snapshot = websocket.receive_json()
        frame_event = websocket.receive_json()

    assert "trace" not in snapshot["snapshot"]
    assert frame_event["type"] == "frame"
    assert frame_event["sequence"] == 1
    assert frame_event["network"] == "kcan"


def test_command_payloads_omit_a_full_trace_and_broadcast_only_deltas() -> None:
    controller = SimulatorController()
    filler = controller.topology.create_bus(CanNetwork.KCAN, "trace-filler")
    for _ in range(2_000):
        filler.send(CanFrame(0x123, b""))
    app = create_app(controller)
    manager = RecordingManager()
    app.state.manager = manager

    response = TestClient(app).post("/api/buttons/0/press")

    assert response.status_code == 200
    assert "trace" not in response.json()
    snapshot_event = manager.broadcasts[-1][0]
    assert snapshot_event["type"] == "snapshot"
    assert "trace" not in snapshot_event["snapshot"]
    assert all(event["type"] != "snapshot" for event in manager.broadcasts[-1][1:])


def test_background_idle_ticks_do_not_broadcast_or_change_endpoint_behavior() -> None:
    ticked = Event()
    app = create_app(TickRecordingController(ticked))
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client:
        assert ticked.wait(timeout=1.0)
        response = client.get("/api/snapshot")

    assert response.status_code == 200
    assert response.json()["application"]["speed_valid"] is False
    assert manager.broadcasts == []


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_prevent_healthy_delivery() -> None:
    manager = ConnectionManager()
    broken = FakeWebSocket(ValueError("socket failed"))
    healthy = FakeWebSocket()
    await manager.connect(cast(WebSocket, broken))
    await manager.connect(cast(WebSocket, healthy))
    event = {"type": "test"}

    await manager.broadcast((event,))

    assert healthy.sent == [event]
    assert cast(WebSocket, broken) not in manager._connections
