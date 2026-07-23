from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from e87canbus.api.main import create_app
from e87canbus.application.intents import (
    SetManualAssistanceLevel,
    SetMaximumAssistance,
)
from e87canbus.application.state import SteeringMode
from e87canbus.composition import build_live_controller_service
from e87canbus.config import default_config, simulator_config
from e87canbus.runtime import (
    ActivateSteeringCurve,
    ExecuteOperatorIntent,
)
from fastapi.testclient import TestClient
from registry_test_support import activate_simulation_devices


def command_app(path: Path):
    return create_app(
        config=replace(simulator_config(), tick_interval_s=60.0),
        profile_database_path=path,
    )


def definition_json() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "points": [
            {"speed_deci_kph": speed, "assistance_per_mille": assistance}
            for speed, assistance in zip(
                (0, 100, 200, 300, 600, 1000, 1600, 2500),
                (1000, 880, 760, 640, 360, 0, 0, 0),
                strict=True,
            )
        ],
    }


def test_set_commands_are_small_explicit_and_idempotent(tmp_path: Path) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
        activate_simulation_devices(client.app.state.controller_service)
        first = client.put("/api/commands/maximum-assistance", json={"enabled": True})
        repeated = client.put("/api/commands/maximum-assistance", json={"enabled": True})
        mode = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 4},
        )
        repeated_mode = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 4},
        )
        disabled = client.put("/api/commands/maximum-assistance", json={"enabled": False})
        snapshot = client.app.state.controller_service.snapshot()

    assert first.json()["accepted"] is True
    assert set(first.json()) == {"accepted", "boot_id", "revision"}
    assert repeated.json()["boot_id"] == first.json()["boot_id"]
    assert repeated.json()["revision"] > first.json()["revision"]
    assert mode.status_code == repeated_mode.status_code == disabled.status_code == 200
    assert repeated_mode.json()["revision"] > mode.json()["revision"]
    assert snapshot.application.maximum_assistance_active is False
    assert snapshot.application.steering_mode.value == "manual"
    assert snapshot.application.manual_assistance_level == 4


def test_manual_level_validation_uses_the_server_steering_configuration(
    tmp_path: Path,
) -> None:
    config = replace(
        simulator_config(),
        tick_interval_s=60.0,
        steering=replace(simulator_config().steering, manual_level_count=3),
    )
    app = create_app(config=config, profile_database_path=tmp_path / "app.sqlite3")

    with TestClient(app) as client:
        activate_simulation_devices(client.app.state.controller_service)
        accepted = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 2},
        )
        rejected = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 3},
        )

    assert accepted.status_code == 200
    assert rejected.status_code == 422
    assert rejected.json()["error"] == {
        "code": "validation_error",
        "message": "manual assistance level must be between 0 and 2",
    }


def test_relative_adjustment_from_max_restores_remembered_level_before_adjusting(
    tmp_path: Path,
) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
        activate_simulation_devices(client.app.state.controller_service)
        client.put("/api/commands/manual-assistance-level", json={"level": 4})
        client.put("/api/commands/maximum-assistance", json={"enabled": True})

        restored = client.post(
            "/api/commands/manual-assistance-adjustment",
            json={"delta": -1},
        )
        first_snapshot = client.app.state.controller_service.snapshot().application
        adjusted = client.post(
            "/api/commands/manual-assistance-adjustment",
            json={"delta": -1},
        )
        second_snapshot = client.app.state.controller_service.snapshot().application

    assert restored.status_code == adjusted.status_code == 200
    assert first_snapshot.maximum_assistance_active is False
    assert first_snapshot.steering_mode is SteeringMode.MANUAL
    assert first_snapshot.manual_assistance_level == 4
    assert second_snapshot.manual_assistance_level == 3


@pytest.mark.parametrize("delta", [-2, 0, 2])
def test_relative_adjustment_rejects_more_than_one_stage(
    tmp_path: Path,
    delta: int,
) -> None:
    with TestClient(command_app(tmp_path / f"app-{delta}.sqlite3")) as client:
        response = client.post(
            "/api/commands/manual-assistance-adjustment",
            json={"delta": delta},
        )

    assert response.status_code == 422


def test_saved_profile_and_unsaved_curve_commands_are_distinct(tmp_path: Path) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
        activate_simulation_devices(client.app.state.controller_service)
        created = client.post(
            "/api/steering/profiles",
            json={"name": "Dry", "definition": definition_json()},
        ).json()
        saved = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": created["profile_id"],
                "expected_revision": created["revision"],
            },
        )
        repeated_saved = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": created["profile_id"],
                "expected_revision": created["revision"],
            },
        )
        saved_state = client.app.state.controller_service.snapshot().application
        unsaved_definition = definition_json()
        unsaved_definition["points"][1]["assistance_per_mille"] = 870
        unsaved = client.put(
            "/api/commands/steering-curve",
            json={"definition": unsaved_definition},
        )
        unsaved_state = client.app.state.controller_service.snapshot().application

    assert saved.status_code == repeated_saved.status_code == unsaved.status_code == 200
    assert repeated_saved.json()["revision"] > saved.json()["revision"]
    assert saved_state.active_steering_curve.saved_profile_id == created["profile_id"]
    assert saved_state.active_steering_curve.saved_profile_revision == created["revision"]
    assert [
        {
            "speed_deci_kph": point.speed_deci_kph,
            "assistance_per_mille": point.assistance_per_mille,
        }
        for point in unsaved_state.active_steering_curve.definition.points
    ] == unsaved_definition["points"]
    assert unsaved_state.active_steering_curve.saved_profile_id is None


def test_commands_are_strict_and_active_state_has_no_http_read(tmp_path: Path) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
        invalid = client.put(
            "/api/commands/maximum-assistance",
            json={"enabled": True, "toggle": True},
        )
        active_state = client.get("/api/steering/curve-state")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert active_state.status_code == 404


def test_each_semantic_http_use_case_submits_one_correct_typed_input(
    tmp_path: Path,
) -> None:
    app = command_app(tmp_path / "app.sqlite3")
    submissions: list[object] = []

    with TestClient(app) as client:
        created = client.post(
            "/api/steering/profiles",
            json={"name": "Dry", "definition": definition_json()},
        ).json()

        def record(work: object) -> Future[int]:
            submissions.append(work)
            future: Future[int] = Future()
            future.set_result(10 + len(submissions))
            return future

        app.state.controller_service.submit = record
        maximum = client.put(
            "/api/commands/maximum-assistance",
            json={"enabled": True},
        )
        mode = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 3},
        )
        draft = client.put(
            "/api/commands/steering-curve",
            json={"definition": definition_json()},
        )
        saved = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": created["profile_id"],
                "expected_revision": created["revision"],
            },
        )

    assert all(response.status_code == 200 for response in (maximum, mode, draft, saved))
    assert submissions[0] == ExecuteOperatorIntent(SetMaximumAssistance(True))
    assert submissions[1] == ExecuteOperatorIntent(SetManualAssistanceLevel(3))
    assert isinstance(submissions[2], ActivateSteeringCurve)
    assert submissions[2].saved_profile_id is None
    assert submissions[2].saved_profile_revision is None
    assert isinstance(submissions[3], ActivateSteeringCurve)
    assert submissions[3].saved_profile_id == created["profile_id"]
    assert submissions[3].saved_profile_revision == created["revision"]
    assert submissions[3].definition == submissions[2].definition
    assert len(submissions) == 4


def test_live_mode_accepts_semantic_commands_and_rejects_dev_actions(
    tmp_path: Path,
) -> None:
    disabled = replace(
        default_config(),
        can_networks=tuple(
            replace(network, enabled=False) for network in default_config().can_networks
        ),
        tick_interval_s=60.0,
    )
    app = create_app(
        controller_service=build_live_controller_service(config=disabled),
        profile_database_path=tmp_path / "app.sqlite3",
    )

    with TestClient(app) as client:
        profile = client.post(
            "/api/steering/profiles",
            json={"name": "Dry", "definition": definition_json()},
        ).json()
        maximum = client.put("/api/commands/maximum-assistance", json={"enabled": True})
        mode = client.put(
            "/api/commands/manual-assistance-level",
            json={"level": 3},
        )
        normal = client.put("/api/commands/maximum-assistance", json={"enabled": False})
        activated = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": profile["profile_id"],
                "expected_revision": profile["revision"],
            },
        )
        dev_action = client.post("/api/dev/simulation/reset")
        application = app.state.controller_service.snapshot().application

    for response in (maximum, mode, normal, activated):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "feature_unavailable"
    assert application.maximum_assistance_active is False
    assert application.steering_mode is SteeringMode.AUTO
    assert application.manual_assistance_level == 0
    assert application.active_steering_curve.saved_profile_id is None
    assert dev_action.status_code == 404
