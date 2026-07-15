import asyncio
import json
import time
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from typing import Any, cast

import pytest
from e87canbus.api.internal.websocket import ConnectionManager
from e87canbus.api.main import create_app, socket_origin_policy
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.composition import ControllerMode, build_controller_service
from e87canbus.config import SimulationConfig, TxPolicyConfig, simulator_config
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.runtime import SimulatedControllerRuntime, SimulatorSnapshot
from fastapi import WebSocket
from fastapi.testclient import TestClient


def make_app(*, inbox_capacity: int = 64):
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1_000),
        tick_interval_s=60.0,
        runtime_inbox_capacity=inbox_capacity,
    )
    return make_app_for_config(config)


def make_app_for_config(
    config,
    *,
    steering_controller_factory=SimulatedSteeringController,
):
    profile_directory = TemporaryDirectory()
    service = build_controller_service(
        ControllerMode.SIMULATED,
        config=config,
        steering_controller_factory=steering_controller_factory,
    )
    app = create_app(
        controller_service=service,
        profile_database_path=Path(profile_directory.name) / "profiles.sqlite3",
    )
    app.state.test_profile_directory = profile_directory
    return app


def simulator_snapshot() -> SimulatorSnapshot:
    runtime = SimulatedControllerRuntime()
    runtime.start()
    return runtime.snapshot()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(make_app()) as test_client:
        yield test_client


class RecordingManager:
    def __init__(self) -> None:
        self.broadcasts: list[Sequence[dict[str, Any]]] = []

    async def broadcast(self, events: Sequence[dict[str, Any]]) -> None:
        self.broadcasts.append(events)


class FakeWebSocket:
    def __init__(self) -> None:
        self.error: Exception | None = None
        self.block = False
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, event: dict[str, Any]) -> None:
        if self.block:
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
        self.sent.append(event)


class DisconnectingWebSocket(FakeWebSocket):
    def __init__(self) -> None:
        super().__init__()
        self.on_send: Callable[[], None] | None = None

    async def send_json(self, event: dict[str, Any]) -> None:
        if self.on_send is not None:
            self.on_send()
            await asyncio.sleep(0)
        await super().send_json(event)


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


class RejectingStartupController(SimulatedSteeringController):
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        raise OSError("startup actuator failure")


class RejectingShutdownController(SimulatedSteeringController):
    def set_assistance(self, command: SetSteeringAssistance) -> None:
        if command.reason is SteeringCommandReason.SHUTDOWN:
            raise OSError("shutdown actuator failure")
        super().set_assistance(command)


class BlockingShutdownController(SimulatedSteeringController):
    def __init__(
        self,
        watchdog_timeout_s: float,
        clock: Callable[[], float],
        *,
        block_shutdown: bool,
    ) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.block_shutdown = block_shutdown
        self.entered = Event()
        self.release = Event()

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        if self.block_shutdown and command.reason is SteeringCommandReason.SHUTDOWN:
            self.entered.set()
            assert self.release.wait(timeout=10.0)
        super().set_assistance(command)


def test_health_and_browser_cors(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}

    response = client.options(
        "/api/dev/simulation/devices/button-pad/buttons/0/press",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_socketio_and_fastapi_share_one_asgi_composition(client: TestClient) -> None:
    handshake = client.get("/socket.io/?EIO=4&transport=polling")

    assert handshake.status_code == 200
    assert handshake.text.startswith('0{"sid":')
    sid = json.loads(handshake.text[1:])["sid"]
    session_path = f"/socket.io/?EIO=4&transport=polling&sid={sid}"
    connected = client.post(
        session_path,
        content="40",
        headers={"content-type": "text/plain;charset=UTF-8"},
    )
    packets = client.get(session_path).text.split("\x1e")
    snapshot_packet = next(packet for packet in packets if packet.startswith("42"))
    event, payload = json.loads(snapshot_packet[2:])

    assert connected.status_code == 200
    assert event == "controller.snapshot"
    assert payload["protocol_version"] == 1
    assert payload["revision"] == 1
    assert set(payload["data"]["topic_revisions"].values()) == {1}
    assert client.get("/api/health").status_code == 200


def test_browser_cors_accepts_an_explicit_development_origin() -> None:
    with TemporaryDirectory() as profile_directory:
        app = create_app(
            profile_database_path=Path(profile_directory) / "profiles.sqlite3",
            cors_origins=("http://127.0.0.1:15173",),
        )
        with TestClient(app) as client:
            response = client.options(
                "/api/settings",
                headers={
                    "Origin": "http://127.0.0.1:15173",
                    "Access-Control-Request-Method": "GET",
                },
            )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:15173"


def test_socketio_origin_policy_allows_same_origin_and_exact_development_origins() -> None:
    policy = socket_origin_policy(("http://127.0.0.1:15173",))
    environ = {"wsgi.url_scheme": "http", "HTTP_HOST": "controller.local"}

    assert policy("http://controller.local", environ) is True
    assert policy("http://127.0.0.1:15173", environ) is True
    assert policy(None, environ) is True
    assert policy("http://untrusted.invalid", environ) is False


def test_snapshot_is_revisioned_and_contains_topology(client: TestClient) -> None:
    response = client.get("/api/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert (body["session_id"], body["revision"]) == (1, 1)
    assert body["fatal"] is False
    assert body["trace"] == []
    assert body["application"]["steering_mode"] == "auto"
    assert body["application"]["engine"] == {
        "rpm": {"value": None, "status": "never_observed"},
        "oil_temperature_c": {"value": None, "status": "never_observed"},
        "coolant_temperature_c": {"value": None, "status": "never_observed"},
    }
    assert body["steering_controller"] == {
        "effective_assistance": 0.0,
        "last_command_reason": "speed_never_observed",
        "watchdog_timed_out": False,
    }
    assert body["devices"] == [
        {
            "id": "button_pad",
            "label": "Button pad",
            "status": "online",
            "reason": None,
        },
        {
            "id": "steering_controller",
            "label": "Steering controller",
            "status": "online",
            "reason": None,
        },
    ]
    assert body["led_colours"] == [3] + [0] * 15
    assert [network["id"] for network in body["networks"]] == ["kcan", "ptcan", "fcan"]


def test_failed_first_command_is_published_without_fabricated_reason() -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    app = make_app_for_config(
        config,
        steering_controller_factory=RejectingStartupController,
    )

    with TestClient(app) as client, client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()

    assert initial["snapshot"]["fatal"] is True
    assert initial["snapshot"]["steering_controller"] == {
        "effective_assistance": 0.0,
        "last_command_reason": None,
        "watchdog_timed_out": True,
    }


@pytest.mark.parametrize(
    ("path", "expected_mode"),
    (
        ("/api/dev/simulation/devices/button-pad/buttons/0/press", "manual"),
        ("/api/dev/simulation/devices/button-pad/buttons/0/release", "auto"),
        ("/api/dev/simulation/step", "manual"),
    ),
)
def test_button_commands_return_slim_snapshots(
    client: TestClient,
    path: str,
    expected_mode: str,
) -> None:
    kwargs = {"json": {"button_index": 0}} if path.endswith("/step") else {}
    response = client.post(path, **kwargs)

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == expected_mode
    assert "trace" not in response.json()


def test_reset_starts_a_new_trace_session(client: TestClient) -> None:
    client.post("/api/dev/simulation/devices/button-pad/buttons/0/press")
    client.put(
        "/api/dev/simulation/devices/button_pad/status",
        json={"status": "offline"},
    )

    response = client.post("/api/dev/simulation/reset")

    assert response.status_code == 200
    assert (response.json()["session_id"], response.json()["revision"]) == (2, 1)
    assert response.json()["trace"] == []
    assert response.json()["application"]["steering_mode"] == "auto"
    assert all(device["status"] == "online" for device in response.json()["devices"])


@pytest.mark.parametrize("device_id", ["button_pad", "steering_controller"])
@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("online", None),
        ("degraded", "simulated_degraded"),
        ("offline", "simulated_offline"),
    ],
)
def test_device_status_endpoint_updates_exact_device_and_returns_complete_snapshot(
    client: TestClient,
    device_id: str,
    status: str,
    reason: str | None,
) -> None:
    response = client.put(
        f"/api/dev/simulation/devices/{device_id}/status",
        json={"status": status},
    )

    assert response.status_code == 200
    assert "trace" not in response.json()
    assert [device["id"] for device in response.json()["devices"]] == [
        "button_pad",
        "steering_controller",
    ]
    selected = next(
        device for device in response.json()["devices"] if device["id"] == device_id
    )
    assert (selected["status"], selected["reason"]) == (status, reason)


@pytest.mark.parametrize(
    ("device_id", "body", "expected_status"),
    [
        ("unknown", {"status": "offline"}, 404),
        ("button_pad", {"status": "unknown"}, 422),
        ("button_pad", {"status": "offline", "unexpected": True}, 422),
        ("button_pad", {"status": True}, 422),
        ("button_pad", {"status": 1}, 422),
        ("button_pad", {}, 422),
    ],
)
def test_invalid_device_status_request_does_not_change_devices(
    client: TestClient,
    device_id: str,
    body: dict[str, bool | str],
    expected_status: int,
) -> None:
    before = client.get("/api/snapshot").json()["devices"]

    response = client.put(
        f"/api/dev/simulation/devices/{device_id}/status",
        json=body,
    )

    assert response.status_code == expected_status
    assert client.get("/api/snapshot").json()["devices"] == before


def test_reset_after_shutdown_failure_returns_new_healthy_api_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    app = make_app_for_config(
        config,
        steering_controller_factory=RejectingShutdownController,
    )

    with caplog.at_level("ERROR"), TestClient(app) as client:
        response = client.post("/api/dev/simulation/reset")

    assert response.status_code == 200
    assert (response.json()["session_id"], response.json()["revision"]) == (2, 1)
    assert response.json()["fatal"] is False
    assert "reset replaced simulation session 1 with fatal diagnostics" in caplog.text


def test_invalid_button_index_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/dev/simulation/devices/button-pad/buttons/16/press"
    )

    assert response.status_code == 422
    assert "button_index" in response.json()["error"]["message"]


def test_vehicle_speed_command_emits_external_frame_and_updates_application(
    client: TestClient,
) -> None:
    response = client.put(
        "/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5}
    )

    assert response.status_code == 200
    assert response.json()["application"]["vehicle_speed_kph"] == 42.5
    assert response.json()["application"]["speed_valid"] is True


def test_vehicle_speed_command_rejects_out_of_range_value(client: TestClient) -> None:
    response = client.put(
        "/api/dev/simulation/vehicle/speed", json={"speed_kph": -1.0}
    )

    assert response.status_code == 422
    assert "simulated speed" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/dev/simulation/step", {"button_index": 0, "unexpected": True}),
        (
            "/api/dev/simulation/vehicle/speed",
            {"speed_kph": 42.5, "unexpected": True},
        ),
    ],
)
def test_development_simulation_requests_reject_unknown_fields(
    client: TestClient,
    path: str,
    body: dict[str, bool | float | int],
) -> None:
    method = client.put if "/vehicle/" in path else client.post
    response = method(path, json=body)

    assert response.status_code == 422


def test_vehicle_speed_silence_command_returns_revisioned_snapshot(
    client: TestClient,
) -> None:
    selected = client.put(
        "/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5}
    )

    response = client.post("/api/dev/simulation/vehicle/speed/silence")

    assert response.status_code == 200
    assert response.json()["session_id"] == selected.json()["session_id"]
    assert response.json()["revision"] == selected.json()["revision"]
    assert "trace" not in response.json()


@pytest.mark.parametrize(
    ("path", "body", "field", "expected"),
    [
        ("/api/dev/simulation/vehicle/rpm", {"rpm": 3500}, "rpm", 3500),
        (
            "/api/dev/simulation/vehicle/oil-temperature",
            {"temperature_c": 112.54},
            "oil_temperature_c",
            112.5,
        ),
        (
            "/api/dev/simulation/vehicle/coolant-temperature",
            {"temperature_c": -12.3},
            "coolant_temperature_c",
            -12.3,
        ),
        (
            "/api/dev/simulation/vehicle/oil-temperature",
            {"temperature_c": 110},
            "oil_temperature_c",
            110.0,
        ),
    ],
)
def test_engine_commands_return_complete_slim_snapshot(
    client: TestClient,
    path: str,
    body: dict[str, float | int],
    field: str,
    expected: float | int,
) -> None:
    response = client.put(path, json=body)

    assert response.status_code == 200
    assert response.json()["application"]["engine"][field] == {
        "value": expected,
        "status": "valid",
    }
    assert set(response.json()["application"]["engine"]) == {
        "rpm",
        "oil_temperature_c",
        "coolant_temperature_c",
    }
    assert "trace" not in response.json()


@pytest.mark.parametrize(
    "path",
    [
        "/api/dev/simulation/vehicle/rpm/silence",
        "/api/dev/simulation/vehicle/oil-temperature/silence",
        "/api/dev/simulation/vehicle/coolant-temperature/silence",
    ],
)
def test_engine_silence_commands_are_idempotent(client: TestClient, path: str) -> None:
    first = client.post(path)
    second = client.post(path)

    assert first.status_code == second.status_code == 200
    assert second.json()["application"]["engine"] == first.json()["application"]["engine"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/dev/simulation/vehicle/rpm", {"rpm": -1}),
        ("/api/dev/simulation/vehicle/rpm", {"rpm": 12_001}),
        ("/api/dev/simulation/vehicle/rpm", {"rpm": 3500, "unexpected": 1}),
        ("/api/dev/simulation/vehicle/oil-temperature", {"temperature_c": -40.1}),
        ("/api/dev/simulation/vehicle/coolant-temperature", {"temperature_c": 250.1}),
        ("/api/dev/simulation/vehicle/rpm", {"rpm": True}),
        ("/api/dev/simulation/vehicle/rpm", {"rpm": "3500"}),
        ("/api/dev/simulation/vehicle/oil-temperature", {"temperature_c": True}),
        ("/api/dev/simulation/vehicle/oil-temperature", {"temperature_c": "110"}),
        ("/api/dev/simulation/vehicle/coolant-temperature", {"temperature_c": True}),
        ("/api/dev/simulation/vehicle/coolant-temperature", {"temperature_c": "98"}),
    ],
)
def test_invalid_engine_request_returns_422_without_changing_state(
    client: TestClient,
    path: str,
    body: dict[str, bool | float | int | str],
) -> None:
    before = client.get("/api/snapshot").json()

    response = client.put(path, json=body)

    assert response.status_code == 422
    after = client.get("/api/snapshot").json()
    assert after["revision"] == before["revision"]
    assert after["application"]["engine"] == before["application"]["engine"]
    assert after["trace"] == before["trace"]


def test_websocket_receives_revisioned_snapshot_and_session_frames(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()
        response = client.post(
            "/api/dev/simulation/devices/button-pad/buttons/0/press"
        )
        snapshot = websocket.receive_json()
        frame = websocket.receive_json()

    assert initial["type"] == "snapshot"
    assert (initial["session_id"], initial["revision"]) == (1, 1)
    assert initial["snapshot"]["application"]["engine"]["rpm"] == {
        "value": None,
        "status": "never_observed",
    }
    assert [device["id"] for device in initial["snapshot"]["devices"]] == [
        "button_pad",
        "steering_controller",
    ]
    assert response.status_code == 200
    assert snapshot["type"] == "snapshot"
    assert "trace" not in snapshot["snapshot"]
    assert frame["type"] == "frame"
    assert (frame["session_id"], frame["sequence"]) == (1, 1)


def test_websocket_heartbeat_keeps_connection_live(client: TestClient) -> None:
    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()
        websocket.send_text("ping")
        heartbeat = websocket.receive_json()
        response = client.post(
            "/api/dev/simulation/devices/button-pad/buttons/0/press"
        )
        snapshot = websocket.receive_json()

    assert initial["type"] == "snapshot"
    assert heartbeat == {"type": "heartbeat"}
    assert response.status_code == 200
    assert snapshot["type"] == "snapshot"


def test_reconnecting_websocket_receives_current_engine_shape(client: TestClient) -> None:
    selected = client.put("/api/dev/simulation/vehicle/rpm", json={"rpm": 4200})
    assert selected.status_code == 200

    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()

    assert initial["type"] == "snapshot"
    assert initial["snapshot"]["application"]["engine"] == {
        "rpm": {"value": 4200, "status": "valid"},
        "oil_temperature_c": {"value": None, "status": "never_observed"},
        "coolant_temperature_c": {"value": None, "status": "never_observed"},
    }


def test_reconnecting_websocket_receives_complete_current_device_shape(
    client: TestClient,
) -> None:
    selected = client.put(
        "/api/dev/simulation/devices/steering_controller/status",
        json={"status": "degraded"},
    )
    assert selected.status_code == 200

    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()

    assert initial["snapshot"]["devices"] == selected.json()["devices"]


def test_command_publications_are_ordered_and_contain_only_trace_deltas() -> None:
    app = make_app()
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=3) as pool:
        press = pool.submit(
            client.post,
            "/api/dev/simulation/devices/button-pad/buttons/0/press",
        )
        release = pool.submit(
            client.post,
            "/api/dev/simulation/devices/button-pad/buttons/0/release",
        )
        assert press.result().status_code == 200
        assert release.result().status_code == 200

    snapshots = [
        event
        for events in manager.broadcasts
        for event in events
        if event["type"] == "snapshot"
    ]
    frames = [
        event for events in manager.broadcasts for event in events if event["type"] == "frame"
    ]
    assert 1 <= len(snapshots) <= 2
    assert all(event["type"] == "snapshot" for event in snapshots)
    assert all("trace" not in event["snapshot"] for event in snapshots)
    assert [frame["sequence"] for frame in frames] == sorted(frame["sequence"] for frame in frames)


def test_reset_cannot_interleave_with_another_operation() -> None:
    app = make_app()
    manager = RecordingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        press = pool.submit(
            client.post,
            "/api/dev/simulation/devices/button-pad/buttons/0/press",
        )
        reset = pool.submit(client.post, "/api/dev/simulation/reset")
        assert press.result().status_code == 200
        assert reset.result().status_code == 200

    sessions = [events[0]["session_id"] for events in manager.broadcasts]
    assert sessions == sorted(sessions)
    for events in manager.broadcasts:
        session_id = events[0]["session_id"]
        assert all(event["session_id"] == session_id for event in events)


def test_controller_inbox_overflow_returns_503_and_service_recovers() -> None:
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1_000),
        tick_interval_s=60.0,
        runtime_inbox_capacity=1,
    )
    controllers: list[BlockingShutdownController] = []

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> BlockingShutdownController:
        controller = BlockingShutdownController(
            watchdog_timeout_s,
            clock,
            block_shutdown=not controllers,
        )
        controllers.append(controller)
        return controller

    app = make_app_for_config(config, steering_controller_factory=build_controller)

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(
            client.post,
            "/api/dev/simulation/reset",
        )
        controller = controllers[0]
        assert controller.entered.wait(timeout=1.0)
        second = pool.submit(
            client.post,
            "/api/dev/simulation/devices/button-pad/buttons/0/release",
        )
        deadline = time.monotonic() + 1.0
        while app.state.controller_service.inbox_depth != 1 and time.monotonic() < deadline:
            pass

        overloaded = pool.submit(
            client.post,
            "/api/dev/simulation/step",
            json={"button_index": 0},
        )
        try:
            overloaded_response = overloaded.result(timeout=1.0)
        finally:
            controller.release.set()

        assert overloaded_response.status_code == 503
        assert first.result().status_code == 200
        assert second.result().status_code == 200
        assert (
            client.post(
                "/api/dev/simulation/devices/button-pad/buttons/0/press"
            ).status_code
            == 200
        )


def test_fatal_timer_is_published_and_scheduling_resumes_after_reset() -> None:
    session_count = 0

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> SimulatedSteeringController:
        nonlocal session_count
        session_count += 1
        controller_type = (
            FailingFirstSessionController if session_count == 1 else SimulatedSteeringController
        )
        return controller_type(watchdog_timeout_s, clock)

    config = replace(
        simulator_config(),
        simulation=SimulationConfig(),
        tx_policy=TxPolicyConfig(max_frames_per_network_window=1_000),
        tick_interval_s=0.01,
    )
    app = make_app_for_config(
        config,
        steering_controller_factory=build_controller,
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

        reset = client.post("/api/dev/simulation/reset")
        assert (reset.json()["revision"], reset.json()["fatal"]) == (1, False)

        deadline = time.monotonic() + 1.0
        while client.get("/api/snapshot").json()["revision"] == 1:
            assert time.monotonic() < deadline


@pytest.mark.asyncio
async def test_broadcast_failure_is_logged_removed_and_does_not_affect_healthy_client(
    caplog: pytest.LogCaptureFixture,
) -> None:
    manager = ConnectionManager(0.1)
    snapshot = simulator_snapshot()

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


@pytest.mark.asyncio
async def test_stalled_websocket_is_bounded_and_healthy_peer_keeps_event_order() -> None:
    manager = ConnectionManager(0.01)
    snapshot = simulator_snapshot()
    stalled = FakeWebSocket()
    healthy = FakeWebSocket()
    await manager.connect(cast(WebSocket, stalled), lambda: snapshot)
    await manager.connect(cast(WebSocket, healthy), lambda: snapshot)
    stalled.block = True
    events = ({"type": "first"}, {"type": "second"})

    await asyncio.wait_for(manager.broadcast(events), timeout=0.1)

    assert healthy.sent[-2:] == list(events)
    assert cast(WebSocket, stalled) not in manager._connections


@pytest.mark.asyncio
async def test_concurrent_disconnect_does_not_abort_publication() -> None:
    manager = ConnectionManager(0.1)
    snapshot = simulator_snapshot()
    disconnecting = DisconnectingWebSocket()
    disconnected = FakeWebSocket()
    healthy = FakeWebSocket()
    await manager.connect(cast(WebSocket, disconnecting), lambda: snapshot)
    await manager.connect(cast(WebSocket, disconnected), lambda: snapshot)
    await manager.connect(cast(WebSocket, healthy), lambda: snapshot)
    disconnecting.on_send = lambda: manager.disconnect(cast(WebSocket, disconnected))
    event = {"type": "test"}

    await manager.broadcast((event,))

    assert disconnecting.sent[-1] == event
    assert healthy.sent[-1] == event
    assert cast(WebSocket, disconnected) not in manager._connections


@pytest.mark.asyncio
async def test_initial_snapshot_send_is_bounded() -> None:
    manager = ConnectionManager(0.01)
    snapshot = simulator_snapshot()
    stalled = FakeWebSocket()
    stalled.block = True

    connected = await asyncio.wait_for(
        manager.connect(cast(WebSocket, stalled), lambda: snapshot),
        timeout=0.1,
    )

    assert connected is False
    assert cast(WebSocket, stalled) not in manager._connections
