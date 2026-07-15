import json
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

import pytest
from e87canbus.api.main import create_app, socket_origin_policy
from e87canbus.api.models.live import health_state
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.composition import build_controller_service, simulated_selection
from e87canbus.config import SimulationConfig, TxPolicyConfig, simulator_config
from e87canbus.device import DeviceAdapterSelection, DeviceRole, DeviceSource
from e87canbus.service import ControllerMode
from e87canbus.simulation.devices import SimulatedSteeringController
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
    selection=None,
):
    profile_directory = TemporaryDirectory()
    service = build_controller_service(
        ControllerMode.SIMULATED,
        config=config,
        selection=selection,
        steering_controller_factory=steering_controller_factory,
    )
    app = create_app(
        controller_service=service,
        profile_database_path=Path(profile_directory.name) / "profiles.sqlite3",
    )
    app.state.test_profile_directory = profile_directory
    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(make_app()) as test_client:
        yield test_client


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
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json()["status"] == "ready"
    assert client.get("/api/health").status_code == 404

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
    topic_revisions = payload["data"]["topic_revisions"]
    assert topic_revisions["health"] == payload["revision"]
    assert {revision for topic, revision in topic_revisions.items() if topic != "health"} == {1}
    health = payload["data"]["health"]
    assert health["ready"] is True
    assert health["inbox"]["capacity"] == 64
    assert health["persistence"] == {"available": True, "fault": None}
    assert health["publisher"]["running"] is True
    assert health["publisher"]["active_sockets"] == 1
    assert health["publisher"]["trace_ring_capacity"] == 2000
    assert client.get("/health/ready").status_code == 200


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


def test_legacy_snapshot_and_raw_websocket_routes_are_removed(
    client: TestClient,
) -> None:
    assert client.get("/api/snapshot").status_code == 404
    assert "/ws" not in {route.path for route in client.app.routes}


def test_failed_first_command_is_projected_without_fabricated_reason() -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    app = make_app_for_config(
        config,
        steering_controller_factory=RejectingStartupController,
    )

    with TestClient(app):
        snapshot = app.state.controller_service.snapshot()

    assert snapshot.diagnostics.health.fatal is True
    assert snapshot.adapter.steering is not None
    assert snapshot.adapter.steering.effective_assistance == 0.0
    assert snapshot.adapter.steering.last_command_reason is None
    assert snapshot.adapter.steering.watchdog_timed_out is True


@pytest.mark.parametrize(
    ("path", "expected_mode"),
    (
        ("/api/dev/simulation/devices/button-pad/buttons/0/press", "manual"),
        ("/api/dev/simulation/devices/button-pad/buttons/0/release", "auto"),
    ),
)
def test_button_commands_return_acknowledgements(
    client: TestClient,
    path: str,
    expected_mode: str,
) -> None:
    response = client.post(path)

    assert response.status_code == 200
    assert set(response.json()) == {
        "accepted",
        "boot_id",
    }
    assert response.json()["accepted"] is True
    assert client.app.state.controller_service.snapshot().application.steering_mode.value == (
        expected_mode
    )


def test_observer_composition_rejects_emulator_controls() -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    selection = replace(
        simulated_selection(config),
        device_adapters=(
            DeviceAdapterSelection(DeviceRole.BUTTON_PAD, DeviceSource.OBSERVER),
        ),
    )
    app = make_app_for_config(config, selection=selection)

    with TestClient(app) as client:
        response = client.post(
            "/api/dev/simulation/devices/button-pad/buttons/0/press"
        )
        snapshot = app.state.controller_service.snapshot()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "controller_failed"
    assert snapshot.application.steering_mode.value == "auto"
    assert snapshot.adapter.devices[0].source_mode is DeviceSource.OBSERVER
    assert snapshot.adapter.devices[0].observed_led_colours is None


def test_reset_starts_a_new_trace_session(client: TestClient) -> None:
    client.post("/api/dev/simulation/devices/button-pad/buttons/0/press")

    response = client.post("/api/dev/simulation/reset")

    assert response.status_code == 200
    snapshot = client.app.state.controller_service.snapshot()
    assert response.json() == {"accepted": True, "boot_id": snapshot.boot_id}
    assert snapshot.adapter.simulation_session_id == 2
    assert snapshot.application.steering_mode.value == "auto"
    assert snapshot.adapter.devices[0].source_mode is DeviceSource.EMULATED
    assert snapshot.adapter.devices[0].observed_led_colours == (3,) + (0,) * 15


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
        fatal = app.state.controller_service.snapshot().diagnostics.health.fatal

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "boot_id": app.state.controller_service.boot_id,
    }
    assert fatal is False
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
    snapshot = client.app.state.controller_service.snapshot()
    assert snapshot.application.vehicle_speed_kph == 42.5
    assert snapshot.application.speed_valid is True


def test_vehicle_speed_command_rejects_out_of_range_value(client: TestClient) -> None:
    response = client.put(
        "/api/dev/simulation/vehicle/speed", json={"speed_kph": -1.0}
    )

    assert response.status_code == 422
    assert "simulated speed" in response.json()["error"]["message"]


def test_development_simulation_requests_reject_unknown_fields(
    client: TestClient,
) -> None:
    response = client.put(
        "/api/dev/simulation/vehicle/speed",
        json={"speed_kph": 42.5, "unexpected": True},
    )

    assert response.status_code == 422


def test_vehicle_speed_silence_command_returns_current_acknowledgement(
    client: TestClient,
) -> None:
    selected = client.put(
        "/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5}
    )

    response = client.post("/api/dev/simulation/vehicle/speed/silence")

    assert response.status_code == 200
    assert response.json() == selected.json()


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
def test_engine_commands_update_the_canonical_service_projection(
    client: TestClient,
    path: str,
    body: dict[str, float | int],
    field: str,
    expected: float | int,
) -> None:
    response = client.put(path, json=body)

    assert response.status_code == 200
    engine = client.app.state.controller_service.snapshot().application.engine
    observed = getattr(engine, field)
    assert observed.value == expected
    assert observed.status.value == "valid"


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
    first_engine = client.app.state.controller_service.snapshot().application.engine
    second = client.post(path)
    second_engine = client.app.state.controller_service.snapshot().application.engine

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert second_engine == first_engine


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
    before = client.app.state.controller_service.snapshot()

    response = client.put(path, json=body)

    assert response.status_code == 422
    after = client.app.state.controller_service.snapshot()
    assert after.revision == before.revision
    assert after.application.engine == before.application.engine


def test_concurrent_reset_and_action_acknowledgements_cannot_name_other_work() -> None:
    app = make_app()

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        press = pool.submit(
            client.post,
            "/api/dev/simulation/devices/button-pad/buttons/0/press",
        )
        reset = pool.submit(client.post, "/api/dev/simulation/reset")
        press_response = press.result()
        reset_response = reset.result()
        assert press_response.status_code == 200
        assert reset_response.status_code == 200
        assert press_response.json() == reset_response.json() == {
            "accepted": True,
            "boot_id": app.state.controller_service.boot_id,
        }
        assert app.state.controller_service.snapshot().adapter.simulation_session_id == 2


def test_controller_inbox_overflow_latches_fault_and_stops_normal_ingestion() -> None:
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
            client.put,
            "/api/dev/simulation/vehicle/speed",
            json={"speed_kph": 42.5},
        )
        try:
            overloaded_response = overloaded.result(timeout=1.0)
        finally:
            controller.release.set()

        assert overloaded_response.status_code == 503
        assert first.result().status_code == 200
        assert second.result().status_code == 503
        deadline = time.monotonic() + 1.0
        while app.state.controller_service.ready and time.monotonic() < deadline:
            pass
        service = app.state.controller_service
        assert service.stopped_event.wait(timeout=1.0)
        snapshot = service.snapshot()
        projected_health = health_state(snapshot)
        assert service.ready is False
        assert snapshot.service.inbox.overflow_latched is True
        assert snapshot.diagnostics.health.fatal is True
        assert snapshot.diagnostics.health.inbox_overflow_fault is not None
        assert all(item.fault is None for item in snapshot.diagnostics.health.networks)
        assert projected_health.fatal is True
        assert projected_health.last_fatal_fault is not None
        assert projected_health.last_fatal_fault.kind == "inbox_overflow"
        assert (
            client.post(
                "/api/dev/simulation/devices/button-pad/buttons/0/press"
            ).status_code
            == 503
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

    with TestClient(app) as client:
        deadline = time.monotonic() + 1.0
        while not app.state.controller_service.snapshot().diagnostics.health.fatal:
            assert time.monotonic() < deadline

        reset = client.post("/api/dev/simulation/reset")
        assert reset.status_code == 200
        assert reset.json() == {
            "accepted": True,
            "boot_id": app.state.controller_service.boot_id,
        }
        assert app.state.controller_service.snapshot().diagnostics.health.fatal is False

        initial_revision = app.state.controller_service.snapshot().revision
        deadline = time.monotonic() + 1.0
        while app.state.controller_service.snapshot().revision == initial_revision:
            assert time.monotonic() < deadline
