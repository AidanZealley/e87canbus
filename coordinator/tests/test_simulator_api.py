import asyncio
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from typing import Any, cast

import pytest
from e87canbus.api.simulator import ConnectionManager, create_app
from e87canbus.application.events import SetSteeringAssistance
from e87canbus.config import SimulationConfig, TxPolicyConfig, simulator_config
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.engine import SimulationEngine, SimulatorSnapshot
from fastapi import WebSocket
from fastapi.testclient import TestClient


def make_app(*, command_queue_capacity: int = 64):
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(command_queue_capacity=command_queue_capacity),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1_000),
        tick_interval_s=60.0,
    )
    return create_app(SimulationEngine(config=config))


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(make_app()) as test_client:
        yield test_client


class RecordingManager:
    def __init__(self) -> None:
        self.broadcasts: list[Sequence[dict[str, Any]]] = []

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        self.broadcasts.append(events)


class BlockingManager(RecordingManager):
    def __init__(self) -> None:
        super().__init__()
        self.entered = Event()
        self.release = Event()
        self._blocked = False

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        await super().broadcast(events)
        if not self._blocked:
            self._blocked = True
            self.entered.set()
            await asyncio.to_thread(self.release.wait)


class FakeWebSocket:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, event: dict[str, Any]) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(event)


class FailingFirstSessionController(SimulatedSteeringController):
    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.attempts = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.attempts += 1
        if self.attempts == 2:
            raise OSError("timer actuator failure")
        super().set_assistance(command)


def test_health_and_browser_cors(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}

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


def test_snapshot_is_revisioned_and_contains_topology(client: TestClient) -> None:
    response = client.get("/api/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert (body["session_id"], body["revision"]) == (1, 1)
    assert body["fatal"] is False
    assert body["trace"] == []
    assert body["application"]["steering_mode"] == "auto"
    assert body["steering_controller"] == {
        "assistance": 0.0,
        "reason": "speed_unavailable",
        "watchdog_timed_out": False,
    }
    assert body["led_colours"] == {"0": 3, "3": 0}
    assert [network["id"] for network in body["networks"]] == ["kcan", "ptcan", "fcan"]


@pytest.mark.parametrize(
    ("path", "expected_mode"),
    (
        ("/api/buttons/0/press", "manual"),
        ("/api/buttons/0/release", "auto"),
        ("/api/step", "manual"),
    ),
)
def test_button_commands_return_slim_snapshots(
    client: TestClient,
    path: str,
    expected_mode: str,
) -> None:
    kwargs = {"json": {"button_index": 0}} if path == "/api/step" else {}
    response = client.post(path, **kwargs)

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == expected_mode
    assert "trace" not in response.json()


def test_reset_starts_a_new_trace_session(client: TestClient) -> None:
    client.post("/api/buttons/0/press")

    response = client.post("/api/reset")

    assert response.status_code == 200
    assert (response.json()["session_id"], response.json()["revision"]) == (2, 1)
    assert response.json()["trace"] == []
    assert response.json()["application"]["steering_mode"] == "auto"


def test_invalid_button_index_returns_validation_error(client: TestClient) -> None:
    response = client.post("/api/buttons/16/press")

    assert response.status_code == 422
    assert "button_index" in response.json()["detail"]


def test_vehicle_speed_command_emits_external_frame_and_updates_application(
    client: TestClient,
) -> None:
    response = client.post("/api/vehicle/speed", json={"speed_kph": 42.5})

    assert response.status_code == 200
    assert response.json()["application"]["vehicle_speed_kph"] == 42.5
    assert response.json()["application"]["speed_valid"] is True


def test_vehicle_speed_command_rejects_out_of_range_value(client: TestClient) -> None:
    response = client.post("/api/vehicle/speed", json={"speed_kph": -1.0})

    assert response.status_code == 422
    assert "simulated speed" in response.json()["detail"]


def test_websocket_receives_revisioned_snapshot_and_session_frames(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()
        response = client.post("/api/buttons/0/press")
        snapshot = websocket.receive_json()
        frame = websocket.receive_json()

    assert initial["type"] == "snapshot"
    assert (initial["session_id"], initial["revision"]) == (1, 1)
    assert response.status_code == 200
    assert snapshot["type"] == "snapshot"
    assert "trace" not in snapshot["snapshot"]
    assert frame["type"] == "frame"
    assert (frame["session_id"], frame["sequence"]) == (1, 1)


def test_command_publications_are_ordered_and_contain_only_trace_deltas() -> None:
    app = make_app()
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        press = pool.submit(client.post, "/api/buttons/0/press")
        release = pool.submit(client.post, "/api/buttons/0/release")
        assert press.result().status_code == 200
        assert release.result().status_code == 200

    snapshots = [events[0] for events in manager.broadcasts]
    frames = [
        event
        for events in manager.broadcasts
        for event in events
        if event["type"] == "frame"
    ]
    assert len(snapshots) == 2
    assert all(event["type"] == "snapshot" for event in snapshots)
    assert all("trace" not in event["snapshot"] for event in snapshots)
    assert [frame["sequence"] for frame in frames] == sorted(frame["sequence"] for frame in frames)


def test_reset_cannot_interleave_with_another_operation() -> None:
    app = make_app()
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        press = pool.submit(client.post, "/api/buttons/0/press")
        reset = pool.submit(client.post, "/api/reset")
        assert press.result().status_code == 200
        assert reset.result().status_code == 200

    sessions = [events[0]["session_id"] for events in manager.broadcasts]
    assert sessions == sorted(sessions)
    for events in manager.broadcasts:
        session_id = events[0]["session_id"]
        assert all(event["session_id"] == session_id for event in events)


def test_command_queue_overflow_returns_503_and_engine_recovers() -> None:
    app = make_app(command_queue_capacity=1)
    manager = BlockingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, "/api/buttons/0/press")
        assert manager.entered.wait(timeout=1.0)
        second = pool.submit(client.post, "/api/buttons/0/release")
        deadline = time.monotonic() + 1.0
        while app.state.command_queue.qsize() != 1 and time.monotonic() < deadline:
            pass

        overloaded = client.post("/api/step", json={"button_index": 0})
        manager.release.set()

        assert overloaded.status_code == 503
        assert first.result().status_code == 200
        assert second.result().status_code == 200
        assert client.post("/api/buttons/0/press").status_code == 200


def test_fatal_timer_is_published_and_scheduling_resumes_after_reset() -> None:
    session_count = 0

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> SimulatedSteeringController:
        nonlocal session_count
        session_count += 1
        controller_type = (
            FailingFirstSessionController
            if session_count == 1
            else SimulatedSteeringController
        )
        return controller_type(watchdog_timeout_s, clock)

    config = replace(
        simulator_config(),
        simulation=SimulationConfig(command_queue_capacity=64),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1_000),
        tick_interval_s=0.01,
    )
    app = create_app(
        SimulationEngine(
            config=config,
            steering_controller_factory=build_controller,
        )
    )
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client:
        deadline = time.monotonic() + 1.0
        while not any(
            event["type"] == "snapshot" and event["snapshot"]["fatal"]
            for events in manager.broadcasts
            for event in events
        ):
            assert time.monotonic() < deadline

        reset = client.post("/api/reset")
        assert (reset.json()["revision"], reset.json()["fatal"]) == (1, False)

        deadline = time.monotonic() + 1.0
        while client.get("/api/snapshot").json()["revision"] == 1:
            assert time.monotonic() < deadline


@pytest.mark.asyncio
async def test_broadcast_failure_is_logged_removed_and_does_not_affect_healthy_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ConnectionManager()
    snapshot = SimulationEngine().snapshot()
    def get_snapshot() -> SimulatorSnapshot:
        return snapshot
    broken = FakeWebSocket()
    healthy = FakeWebSocket()
    await manager.connect(cast(WebSocket, broken), get_snapshot)
    await manager.connect(cast(WebSocket, healthy), get_snapshot)
    broken.error = ValueError("socket failed")
    event = {"type": "test"}

    await manager.broadcast((event,))

    assert healthy.sent[-1] == event
    assert cast(WebSocket, broken) not in manager._connections
    assert "removing failed simulator WebSocket" in caplog.text
