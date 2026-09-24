"""The simulated pad consumes the production configuration and input routes."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

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
from e87canbus.runners.simulation.devices.button_pad import SIMULATED_BUTTON_PAD_ID
from fastapi.testclient import TestClient


def wait_until(predicate: Callable[[], bool], timeout: float = 2) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("simulated pad did not update")


def test_initial_scene_and_replacement_report_status(tmp_path: Path) -> None:
    app = create_app(profile_database_path=tmp_path / "state.sqlite3")
    with TestClient(app) as browser:
        pad = app.state.simulated_button_pad
        initial = pad.applied
        assert initial is not None
        assert initial.generation == 0
        assert len(initial.scene.buttons) == 16
        assert browser.get("/health/live").status_code == 200
        repository = app.state.device_state_repository
        status = repository.get_status(SIMULATED_BUTTON_PAD_ID, DeviceRole.BUTTON_PAD)
        assert status is not None
        assert status.status.applied_configuration_generation == initial.generation
        assert app.state.device_configuration.subscriber_count == 1

        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        app.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        wait_until(lambda: pad.applied is not None and pad.applied.generation == 1)
        wait_until(
            lambda: (
                (reported := repository.get_status(SIMULATED_BUTTON_PAD_ID, DeviceRole.BUTTON_PAD))
                is not None
                and reported.status.applied_configuration_generation == 1
            )
        )
        status = repository.get_status(SIMULATED_BUTTON_PAD_ID, DeviceRole.BUTTON_PAD)
        assert status is not None
        assert status.status.applied_configuration_generation == 1
        assert pad.applied.scene.buttons[5].colour == [12, 34, 56]

    assert app.state.device_configuration.subscriber_count == 0


def test_tap_posts_one_canonical_press_and_no_retry(tmp_path: Path) -> None:
    app = create_app(profile_database_path=tmp_path / "state.sqlite3", clock=lambda: 123.5)
    with TestClient(app) as browser:
        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        loop = app.state.controller_loop
        loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        submitted: list[object] = []
        original_submit = loop.submit

        def record(work: object):
            submitted.append(work)
            return original_submit(work)

        loop.submit = record
        response = browser.post("/api/dev/simulation/button-pad/tap", json={"button_index": 5})
        assert response.status_code == 200
        assert submitted == [ButtonPressed(5, observed_at=123.5)]
        assert loop.snapshot().application.steering_mode is SteeringMode.MANUAL


def test_restart_reuses_generation(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    first = create_app(profile_database_path=database)
    with TestClient(first):
        profile = ActiveButtonProfile(
            "test",
            button_profile_definition_with(
                {5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}
            ),
        )
        repository = first.state.button_profile_repository
        saved = repository.create_profile("test", profile.definition)
        repository.select_profile(saved.profile_id, saved.revision)
        first.state.controller_loop.submit(ActivateButtonProfile(profile)).result(timeout=2)
        wait_until(lambda: first.state.simulated_button_pad.applied.generation == 1)

    restarted = create_app(profile_database_path=database)
    with TestClient(restarted):
        assert restarted.state.simulated_button_pad.applied.generation == 1
        stored = restarted.state.device_state_repository.get_configuration(
            SIMULATED_BUTTON_PAD_ID, DeviceRole.BUTTON_PAD
        )
        assert stored is not None
        assert stored.generation == 1
