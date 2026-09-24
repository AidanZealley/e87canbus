"""Production device HTTP inputs through authentication and the controller inbox."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from e87canbus.api.auth import DeviceRole
from e87canbus.api.main import create_app
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.events import ButtonPressed
from e87canbus.domain.intents import ToggleAutomaticAssistance
from e87canbus.domain.state import SteeringMode
from e87canbus.kernel import ActivateButtonProfile
from fastapi.testclient import TestClient
from test_transport_authorization import (
    DEVICE_ID,
    authenticator,
    basic_headers,
    console_headers,
)

STATUS = {
    "status_version": 1,
    "applied_configuration_generation": 2,
    "configuration_error": None,
    "device": {},
}
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def device_app(tmp_path: Path):
    return create_app(
        profile_database_path=tmp_path / "devices.sqlite3",
        authenticator=authenticator(trust_test_client=True),
        clock=lambda: 123.5,
        utc_clock=lambda: NOW,
    )


def test_status_uses_authenticated_identity_and_utc_receipt(tmp_path: Path) -> None:
    with TestClient(device_app(tmp_path)) as client:
        response = client.post(
            "/api/devices/status",
            headers=console_headers(role=DeviceRole.BUTTON_PAD),
            json=STATUS,
        )
        stored = client.app.state.device_state_repository.get_status(
            DEVICE_ID, DeviceRole.BUTTON_PAD
        )

    assert response.status_code == 204
    assert response.content == b""
    assert stored is not None
    assert stored.status.model_dump() == STATUS
    assert stored.received_at_utc == "2026-09-24T12:00:00.000000Z"


@pytest.mark.parametrize(
    ("headers", "body", "expected"),
    [
        (console_headers(role=DeviceRole.BUTTON_PAD), {**STATUS, "device_id": DEVICE_ID}, 422),
        (console_headers(role=DeviceRole.BUTTON_PAD), {**STATUS, "device": {"other": 1}}, 422),
        (console_headers(role=DeviceRole.BUTTON_PAD), {**STATUS, "status_version": 2}, 422),
        (console_headers(role=DeviceRole.SERVOTRONIC_CONTROLLER), {"bad": True}, 403),
        (console_headers(), STATUS, 403),
        (basic_headers(), STATUS, 403),
        ({}, STATUS, 401),
    ],
)
def test_rejected_status_does_not_write(
    tmp_path: Path, headers: dict[str, str], body: dict[str, object], expected: int
) -> None:
    with TestClient(device_app(tmp_path)) as client:
        response = client.post("/api/devices/status", headers=headers, json=body)
        stored = client.app.state.device_state_repository.get_status(
            DEVICE_ID, DeviceRole.BUTTON_PAD
        )

    assert response.status_code == expected
    assert stored is None


def test_press_submits_one_stamped_input_and_evaluates_profile_once(tmp_path: Path) -> None:
    app = device_app(tmp_path)
    with TestClient(app) as client:
        loop = app.state.controller_loop
        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        submitted: list[object] = []
        original_submit = loop.submit

        def record_submit(work: object):
            submitted.append(work)
            return original_submit(work)

        loop.submit = record_submit
        response = client.post(
            "/api/devices/button-pad/presses",
            headers=console_headers(role=DeviceRole.BUTTON_PAD),
            json={"button_index": 5},
        )
        snapshot = loop.snapshot().application

    assert response.status_code == 204
    assert response.content == b""
    assert submitted == [ButtonPressed(5, observed_at=123.5)]
    assert snapshot.steering_mode is SteeringMode.MANUAL


@pytest.mark.parametrize("index", [True, -1, 16, 1.0, "5"])
def test_invalid_press_does_not_submit(tmp_path: Path, index: object) -> None:
    app = device_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/devices/button-pad/presses",
            headers=console_headers(role=DeviceRole.BUTTON_PAD),
            json={"button_index": index},
        )
    assert response.status_code == 422


def test_wrong_role_cannot_submit_press(tmp_path: Path) -> None:
    with TestClient(device_app(tmp_path)) as client:
        response = client.post(
            "/api/devices/button-pad/presses",
            headers=console_headers(role=DeviceRole.SERVOTRONIC_CONTROLLER),
            json={"button_index": 5},
        )
    assert response.status_code == 403
