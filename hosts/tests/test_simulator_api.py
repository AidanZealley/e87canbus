from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from e87canbus.api.main import create_app
from e87canbus.config import simulator_config
from e87canbus.runners.composition import build_simulated_controller_loop
from fastapi.testclient import TestClient


def make_app():
    directory = TemporaryDirectory()
    service = build_simulated_controller_loop(
        config=replace(simulator_config(), tick_interval_s=60.0)
    )
    app = create_app(
        controller_loop=service,
        profile_database_path=Path(directory.name) / "profiles.sqlite3",
    )
    app.state.test_directory = directory
    return app


@pytest.fixture
def client():
    with TestClient(make_app()) as test_client:
        yield test_client


def test_health_and_browser_cors(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json()["status"] == "ready"
    assert client.get("/api/runtime").json()["profile"] == "simulator"
    response = client.options(
        "/api/dev/simulation/vehicle/speed",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_vehicle_speed_command_crosses_decoder_and_updates_application(client: TestClient) -> None:
    response = client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5})
    snapshot = client.app.state.controller_loop.snapshot()
    assert response.status_code == 200
    assert snapshot.application.vehicle_speed_kph == 42.5
    assert snapshot.application.steering_mode.value == "auto"
    assert not hasattr(snapshot.application, "effective_assistance")


def test_vehicle_speed_rejects_out_of_range_value(client: TestClient) -> None:
    response = client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 400})
    assert response.status_code == 422


def test_reset_starts_new_vehicle_session(client: TestClient) -> None:
    client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 42.5})
    response = client.post("/api/dev/simulation/reset")
    snapshot = client.app.state.controller_loop.snapshot()
    assert response.status_code == 200
    assert snapshot.simulation_session_id == 2
    assert snapshot.application.vehicle_speed_kph == 0


def test_project_device_routes_are_absent(client: TestClient) -> None:
    assert (
        client.post("/api/dev/simulation/devices/servotronic_controller/connect").status_code == 404
    )
