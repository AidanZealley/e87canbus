from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from typing import Any

from e87canbus.api.main import create_app
from e87canbus.application.state import SteeringMode
from e87canbus.config import default_config, simulator_config
from e87canbus.runtime import (
    ActivateSteeringCurve,
    SetMaximumAssistance,
    SetSteeringMode,
)
from e87canbus.service import ControllerCommandResult, ControllerMode
from fastapi.testclient import TestClient


def command_app(path: Path):
    return create_app(
        config=replace(simulator_config(), tick_interval_s=60.0),
        profile_database_path=path,
    )


def definition_json() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "interpolation": "linear-v1",
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
        first = client.put(
            "/api/commands/maximum-assistance", json={"enabled": True}
        )
        repeated = client.put(
            "/api/commands/maximum-assistance", json={"enabled": True}
        )
        mode = client.put(
            "/api/commands/steering-mode",
            json={"mode": "manual", "manual_level": 4},
        )
        repeated_mode = client.put(
            "/api/commands/steering-mode",
            json={"mode": "manual", "manual_level": 4},
        )
        disabled = client.put(
            "/api/commands/maximum-assistance", json={"enabled": False}
        )
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


def test_saved_profile_and_unsaved_curve_commands_are_distinct(tmp_path: Path) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
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


def test_commands_are_strict_and_old_mutation_routes_are_removed(tmp_path: Path) -> None:
    with TestClient(command_app(tmp_path / "app.sqlite3")) as client:
        invalid = client.put(
            "/api/commands/maximum-assistance",
            json={"enabled": True, "toggle": True},
        )
        old_routes = (
            client.post("/api/reset"),
            client.post("/api/buttons/0/press"),
            client.post("/api/vehicle/speed", json={"speed_kph": 20.0}),
            client.get("/api/steering/curve-state"),
            client.post(
                "/api/steering/curve-state/activate",
                json={"definition": definition_json()},
            ),
        )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert all(response.status_code == 404 for response in old_routes)


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

        def record(work: object) -> Future[object]:
            submissions.append(work)
            future: Future[object] = Future()
            future.set_result(ControllerCommandResult(10 + len(submissions), False))
            return future

        app.state.controller_service.submit = record
        maximum = client.put(
            "/api/commands/maximum-assistance",
            json={"enabled": True},
        )
        mode = client.put(
            "/api/commands/steering-mode",
            json={"mode": "manual", "manual_level": 3},
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
    assert submissions[0] == SetMaximumAssistance(True)
    assert submissions[1] == SetSteeringMode(SteeringMode.MANUAL, 3)
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
        mode=ControllerMode.LIVE,
        config=disabled,
        profile_database_path=tmp_path / "app.sqlite3",
    )

    with TestClient(app) as client:
        profile = client.post(
            "/api/steering/profiles",
            json={"name": "Dry", "definition": definition_json()},
        ).json()
        maximum = client.put(
            "/api/commands/maximum-assistance", json={"enabled": True}
        )
        mode = client.put(
            "/api/commands/steering-mode",
            json={"mode": "manual", "manual_level": 3},
        )
        normal = client.put(
            "/api/commands/maximum-assistance", json={"enabled": False}
        )
        activated = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": profile["profile_id"],
                "expected_revision": profile["revision"],
            },
        )
        dev_action = client.post("/api/dev/simulation/reset")
        application = app.state.controller_service.snapshot().application

    assert all(
        response.status_code == 200
        for response in (maximum, mode, normal, activated)
    )
    assert application.maximum_assistance_active is False
    assert application.steering_mode is SteeringMode.MANUAL
    assert application.manual_assistance_level == 3
    assert application.active_steering_curve.saved_profile_id == profile["profile_id"]
    assert dev_action.status_code == 404
