import asyncio
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from e87canbus.api.simulator import create_app
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.config import SimulationConfig, simulator_config
from e87canbus.features.steering import BUILT_IN_STEERING_CURVE, CurveInterpolation
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.engine import SimulationEngine
from fastapi.testclient import TestClient


def definition_json(
    *,
    second_assistance: int = 889,
    interpolation: str = "linear-v1",
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "interpolation": interpolation,
        "points": [
            {
                "speed_deci_kph": point.speed_deci_kph,
                "assistance_per_mille": (
                    second_assistance if index == 1 else point.assistance_per_mille
                ),
            }
            for index, point in enumerate(BUILT_IN_STEERING_CURVE.points)
        ],
    }


def profile_payload(name: str = "Dry track", *, second_assistance: int = 850) -> dict[str, Any]:
    return {"name": name, "definition": definition_json(second_assistance=second_assistance)}


def make_app(path: Path, *, engine: SimulationEngine | None = None):
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(command_queue_capacity=64),
        tick_interval_s=60.0,
    )
    return create_app(
        engine or SimulationEngine(config=config),
        profile_database_path=path,
    )


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(make_app(tmp_path / "profiles.sqlite3")) as test_client:
        yield test_client


def create_profile(client: TestClient, name: str = "Dry track") -> dict[str, Any]:
    response = client.post("/api/steering/profiles", json=profile_payload(name))
    assert response.status_code == 201
    return response.json()


def test_profile_crud_serializes_complete_authoritative_values(client: TestClient) -> None:
    initial = client.get("/api/steering/profiles")
    created = create_profile(client)

    assert initial.status_code == 200
    assert len(initial.json()["profiles"]) == 1
    assert set(created) == {
        "profile_id",
        "name",
        "revision",
        "definition",
        "created_at",
        "updated_at",
    }
    assert created["name"] == "Dry track"
    assert created["revision"] == 1
    assert created["definition"] == definition_json(second_assistance=850)
    assert created["created_at"] == created["updated_at"]

    fetched = client.get(f"/api/steering/profiles/{created['profile_id']}")
    updated = client.put(
        f"/api/steering/profiles/{created['profile_id']}",
        json={
            "expected_revision": 1,
            **profile_payload("Wet track", second_assistance=800),
        },
    )
    listed = client.get("/api/steering/profiles")
    deleted = client.delete(
        f"/api/steering/profiles/{created['profile_id']}",
        params={"expected_revision": 2},
    )

    assert fetched.json() == created
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["name"] == "Wet track"
    assert updated.json()["definition"] == definition_json(second_assistance=800)
    assert updated.json()["created_at"] == created["created_at"]
    assert [item["name"] for item in listed.json()["profiles"]] == [
        "Built-in default",
        "Wet track",
    ]
    assert deleted.status_code == 204
    assert client.get(f"/api/steering/profiles/{created['profile_id']}").status_code == 404


def test_api_saves_and_activates_monotone_cubic_profiles_explicitly(
    client: TestClient,
) -> None:
    smooth = definition_json(interpolation="monotone-cubic-v1")

    saved = client.post(
        "/api/steering/profiles",
        json={"name": "Smooth", "definition": smooth},
    )
    activated = client.post(
        "/api/steering/curve-state/activate",
        json={"definition": smooth},
    )

    assert saved.status_code == 201
    assert saved.json()["definition"] == smooth
    assert activated.status_code == 200
    assert activated.json()["definition"] == smooth
    assert activated.json()["supported_interpolations"] == [
        "linear-v1",
        "monotone-cubic-v1",
    ]


def test_api_reports_consumer_supported_versions_when_smooth_activation_is_rejected(
    tmp_path: Path,
) -> None:
    engine = SimulationEngine(
        supported_steering_curve_interpolations=(CurveInterpolation.LINEAR_V1,)
    )

    with TestClient(make_app(tmp_path / "profiles.sqlite3", engine=engine)) as client:
        before = client.get("/api/steering/curve-state").json()
        response = client.post(
            "/api/steering/curve-state/activate",
            json={
                "definition": definition_json(interpolation="monotone-cubic-v1")
            },
        )
        after = client.get("/api/steering/curve-state").json()

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "unsupported_interpolation",
        "message": (
            "steering curve consumer does not support monotone-cubic-v1; "
            "supported interpolations: linear-v1"
        ),
        "supported_interpolations": ["linear-v1"],
    }
    assert after == before


def test_saved_profiles_survive_api_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "profiles.sqlite3"
    with TestClient(make_app(database_path)) as first_client:
        created = create_profile(first_client)

    with TestClient(make_app(database_path)) as restarted_client:
        fetched = restarted_client.get(
            f"/api/steering/profiles/{created['profile_id']}"
        )

    assert fetched.status_code == 200
    assert fetched.json() == created


@pytest.mark.parametrize(
    "payload",
    [
        profile_payload(" Track "),
        {**profile_payload(), "definition": {**definition_json(), "schema_version": 2}},
        {**profile_payload(), "definition": {**definition_json(), "interpolation": "cubic"}},
        {
            **profile_payload(),
            "definition": {**definition_json(), "points": definition_json()["points"][:-1]},
        },
        {
            **profile_payload(),
            "definition": {
                **definition_json(),
                "points": [
                    *definition_json()["points"][:1],
                    {"speed_deci_kph": 101, "assistance_per_mille": 889},
                    *definition_json()["points"][2:],
                ],
            },
        },
        {
            **profile_payload(),
            "definition": {
                **definition_json(),
                "points": [
                    *definition_json()["points"][:2],
                    {"speed_deci_kph": 200, "assistance_per_mille": 900},
                    *definition_json()["points"][3:],
                ],
            },
        },
        {
            **profile_payload(),
            "definition": {
                **definition_json(),
                "points": [
                    {"speed_deci_kph": 0, "assistance_per_mille": 1001},
                    *definition_json()["points"][1:],
                ],
            },
        },
        {
            **profile_payload(),
            "definition": {
                **definition_json(),
                "points": [
                    *definition_json()["points"][:1],
                    {"speed_deci_kph": 100, "assistance_per_mille": 1000.0},
                    *definition_json()["points"][2:],
                ],
            },
        },
    ],
)
def test_domain_validation_errors_use_one_envelope(
    client: TestClient, payload: dict[str, Any]
) -> None:
    response = client.post("/api/steering/profiles", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert isinstance(response.json()["error"]["message"], str)


def test_not_found_name_conflict_and_revision_conflict_are_typed(
    client: TestClient,
) -> None:
    created = create_profile(client)
    duplicate = client.post("/api/steering/profiles", json=profile_payload("dry TRACK"))
    missing = client.get("/api/steering/profiles/11111111-1111-4111-8111-111111111111")
    updated = client.put(
        f"/api/steering/profiles/{created['profile_id']}",
        json={"expected_revision": 1, **profile_payload("Revised")},
    )
    stale = client.put(
        f"/api/steering/profiles/{created['profile_id']}",
        json={"expected_revision": 1, **profile_payload("Stale")},
    )

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "profile_name_conflict"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "profile_not_found"
    assert updated.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"] == {
        "code": "profile_revision_conflict",
        "message": (
            f"steering profile {created['profile_id']} is at revision 2, not 1"
        ),
        "current_revision": 2,
    }
    assert client.get(f"/api/steering/profiles/{created['profile_id']}").json() == updated.json()


def test_stale_delete_preserves_the_newer_profile(client: TestClient) -> None:
    created = create_profile(client)
    updated = client.put(
        f"/api/steering/profiles/{created['profile_id']}",
        json={"expected_revision": 1, **profile_payload("Revised")},
    ).json()

    stale = client.delete(
        f"/api/steering/profiles/{created['profile_id']}",
        params={"expected_revision": 1},
    )

    assert stale.status_code == 409
    assert stale.json()["error"]["current_revision"] == 2
    assert client.get(f"/api/steering/profiles/{created['profile_id']}").json() == updated


def test_apply_and_save_have_distinct_state_owners(client: TestClient) -> None:
    initial_curve = client.get("/api/steering/curve-state").json()
    applied_definition = definition_json(second_assistance=850)

    applied = client.post(
        "/api/steering/curve-state/activate",
        json={"definition": applied_definition},
    )
    catalog_after_apply = client.get("/api/steering/profiles").json()["profiles"]
    saved = create_profile(client, "Saved only")
    curve_after_save = client.get("/api/steering/curve-state").json()

    assert applied.status_code == 200
    assert applied.json()["definition"] == applied_definition
    assert applied.json()["activation_revision"] == initial_curve["activation_revision"] + 1
    assert applied.json()["saved_profile_id"] is None
    assert len(catalog_after_apply) == 1
    assert saved["definition"] == applied_definition
    assert curve_after_save == applied.json()


@pytest.mark.parametrize("mismatch", ["revision", "definition"])
def test_false_saved_provenance_is_rejected(client: TestClient, mismatch: str) -> None:
    saved = create_profile(client)
    request = {
        "definition": saved["definition"],
        "saved_profile_id": saved["profile_id"],
        "saved_profile_revision": saved["revision"],
    }
    if mismatch == "revision":
        request["saved_profile_revision"] = 99
    else:
        request["definition"] = definition_json(second_assistance=800)
    before = client.get("/api/steering/curve-state").json()

    response = client.post("/api/steering/curve-state/activate", json=request)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "saved_provenance_mismatch"
    assert response.json()["error"]["current_revision"] == 1
    assert client.get("/api/steering/curve-state").json() == before


def test_matching_saved_provenance_is_published(client: TestClient) -> None:
    saved = create_profile(client)

    response = client.post(
        "/api/steering/curve-state/activate",
        json={
            "definition": saved["definition"],
            "saved_profile_id": saved["profile_id"],
            "saved_profile_revision": saved["revision"],
        },
    )

    assert response.status_code == 200
    assert response.json()["saved_profile_id"] == saved["profile_id"]
    assert response.json()["saved_profile_revision"] == 1


def test_partial_saved_provenance_is_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/steering/curve-state/activate",
        json={
            "definition": definition_json(),
            "saved_profile_id": "11111111-1111-4111-8111-111111111111",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_concurrent_updates_allow_one_expected_revision_to_win(client: TestClient) -> None:
    created = create_profile(client)
    path = f"/api/steering/profiles/{created['profile_id']}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            client.put,
            path,
            json={"expected_revision": 1, **profile_payload("First")},
        )
        second = pool.submit(
            client.put,
            path,
            json={"expected_revision": 1, **profile_payload("Second")},
        )
        responses = (first.result(), second.result())

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["error"]["current_revision"] == 2
    assert client.get(path).json()["revision"] == 2


class BlockingManager:
    def __init__(self) -> None:
        self.entered = Event()
        self.release = Event()

    async def broadcast(self, _events: Any) -> None:
        self.entered.set()
        await asyncio.to_thread(self.release.wait)


def test_activation_queue_overload_is_bounded(tmp_path: Path) -> None:
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(command_queue_capacity=1),
        tick_interval_s=60.0,
    )
    app = make_app(
        tmp_path / "profiles.sqlite3",
        engine=SimulationEngine(config=config),
    )
    manager = BlockingManager()
    app.state.manager = manager

    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(client.post, "/api/buttons/0/press")
        assert manager.entered.wait(timeout=1.0)
        second = pool.submit(client.post, "/api/buttons/0/release")
        deadline = time.monotonic() + 1.0
        while app.state.command_queue.qsize() != 1 and time.monotonic() < deadline:
            pass
        assert app.state.command_queue.qsize() == 1
        overloaded = client.post(
            "/api/steering/curve-state/activate",
            json={"definition": definition_json(second_assistance=850)},
        )
        manager.release.set()
        assert first.result().status_code == 200
        assert second.result().status_code == 200

    assert overloaded.status_code == 503
    assert overloaded.json()["error"]["code"] == "runtime_queue_full"


class RejectingActivationController(SimulatedSteeringController):
    def __init__(self, watchdog_timeout_s: float, clock: Callable[[], float]) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.auto_commands = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        if command.reason is SteeringCommandReason.AUTO:
            self.auto_commands += 1
            if self.auto_commands == 1:
                raise OSError("activation effect rejected")
        super().set_assistance(command)


def test_save_then_failed_activation_reports_split_result(tmp_path: Path) -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    app = make_app(
        tmp_path / "profiles.sqlite3",
        engine=SimulationEngine(
            config=config,
            steering_controller_factory=RejectingActivationController,
        ),
    )

    with TestClient(app) as client:
        saved = create_profile(client)
        speed = client.post("/api/vehicle/speed", json={"speed_kph": 10.0})
        assert speed.status_code == 200
        with client.websocket_connect("/ws") as websocket:
            initial = websocket.receive_json()
            activation = client.post(
                "/api/steering/curve-state/activate",
                json={
                    "definition": saved["definition"],
                    "saved_profile_id": saved["profile_id"],
                    "saved_profile_revision": saved["revision"],
                },
            )
            fatal_publication = websocket.receive_json()
        fetched = client.get(f"/api/steering/profiles/{saved['profile_id']}")
        curve_state = client.get("/api/steering/curve-state")
        runtime_snapshot = client.get("/api/snapshot")

    assert initial["snapshot"]["fatal"] is False
    assert activation.status_code == 503
    assert activation.json()["error"] == {
        "code": "activation_effect_failed",
        "message": "curve activation committed but its immediate runtime effect failed",
    }
    assert fetched.status_code == 200
    assert fetched.json() == saved
    assert curve_state.status_code == 200
    assert curve_state.json()["definition"] == saved["definition"]
    assert curve_state.json()["saved_profile_id"] == saved["profile_id"]
    assert runtime_snapshot.json()["fatal"] is True
    assert fatal_publication["type"] == "snapshot"
    assert fatal_publication["snapshot"]["fatal"] is True
    assert (
        fatal_publication["snapshot"]["application"]["active_steering_curve"]["definition"]
        == saved["definition"]
    )


def test_websocket_reconnect_snapshot_and_catalog_invalidation_are_authoritative(
    client: TestClient,
) -> None:
    applied_definition = definition_json(second_assistance=850)
    applied = client.post(
        "/api/steering/curve-state/activate",
        json={"definition": applied_definition},
    )
    assert applied.status_code == 200

    with client.websocket_connect("/ws") as websocket:
        initial = websocket.receive_json()
        created = client.post("/api/steering/profiles", json=profile_payload())
        invalidation = websocket.receive_json()

    assert initial["type"] == "snapshot"
    assert (
        initial["snapshot"]["application"]["active_steering_curve"]["definition"]
        == applied_definition
    )
    assert created.status_code == 201
    assert invalidation == {"type": "steering_profile_catalog_changed"}
