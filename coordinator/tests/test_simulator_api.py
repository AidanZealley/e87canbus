from e87canbus.api.simulator import create_app
from e87canbus.simulation.controller import SimulatorController
from fastapi.testclient import TestClient


def make_client() -> TestClient:
    return TestClient(create_app(SimulatorController()))


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
    assert response.json()["led_colours"] == {"0": 3, "3": 0}


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
    assert response.json()["trace"][0]["arbitration_id_hex"] == "0x700"


def test_release_button() -> None:
    client = make_client()
    client.post("/api/buttons/0/press")

    response = client.post("/api/buttons/0/release")

    assert response.status_code == 200
    assert response.json()["application"]["steering_mode"] == "manual"
    assert response.json()["led_colours"] == {"0": 4, "3": 0}


def test_step() -> None:
    client = make_client()

    response = client.post("/api/step", json={"button_index": 0})

    assert response.status_code == 200
    assert response.json()["trace"][0]["data_hex"] == "0001"


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
