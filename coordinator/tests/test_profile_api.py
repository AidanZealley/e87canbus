import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from e87canbus.api.main import create_app
from e87canbus.composition import build_simulated_controller_service
from e87canbus.config import SimulationConfig, simulator_config
from e87canbus.domain.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.domain.steering import BUILT_IN_STEERING_CURVE
from e87canbus.simulation.devices import SimulatedServotronicPeer
from fastapi.testclient import TestClient
from registry_test_support import activate_simulation_devices


def definition_json(
    *,
    second_assistance: int = 889,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
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


def definition_primitive(definition) -> dict[str, Any]:
    return {
        "schema_version": definition.schema_version,
        "points": [
            {
                "speed_deci_kph": point.speed_deci_kph,
                "assistance_per_mille": point.assistance_per_mille,
            }
            for point in definition.points
        ],
    }


def make_app(
    path: Path,
    *,
    config=None,
    servotronic_factory=SimulatedServotronicPeer,
):
    config = config or replace(simulator_config(), tick_interval_s=60.0)
    service = build_simulated_controller_service(
        config=config,
        servotronic_factory=servotronic_factory,
    )
    return create_app(
        controller_service=service,
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
    assert len(initial.json()) == 1
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

    saved = client.get("/api/steering/profile")
    assert saved.status_code == 200
    assert saved.json() == initial.json()[0]

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
    assert [item["name"] for item in listed.json()] == [
        "Built-in default",
        "Wet track",
    ]
    assert deleted.status_code == 204
    assert client.get(f"/api/steering/profiles/{created['profile_id']}").status_code == 404


def test_saved_profile_endpoint_returns_an_editable_builtin_profile(
    client: TestClient,
) -> None:
    saved = client.get("/api/steering/profile").json()

    updated = client.put(
        f"/api/steering/profiles/{saved['profile_id']}",
        json={
            "expected_revision": saved["revision"],
            "name": saved["name"],
            "definition": definition_json(second_assistance=800),
        },
    )

    assert updated.status_code == 200
    assert updated.json()["revision"] == saved["revision"] + 1
    assert client.get("/api/steering/profile").json() == updated.json()


def test_api_saves_and_activates_monotone_cubic_profiles_explicitly(
    client: TestClient,
) -> None:
    activate_simulation_devices(client.app.state.controller_service)
    smooth = definition_json()

    saved = client.post(
        "/api/steering/profiles",
        json={"name": "Smooth", "definition": smooth},
    )
    activated = client.put(
        "/api/commands/steering-curve",
        json={"definition": smooth},
    )
    active = client.app.state.controller_service.snapshot().application

    assert saved.status_code == 201
    assert saved.json()["definition"] == smooth
    assert activated.status_code == 200
    assert set(activated.json()) == {"accepted", "boot_id", "revision"}
    assert definition_primitive(active.active_steering_curve.definition) == smooth


def test_saved_profiles_survive_api_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "profiles.sqlite3"
    with TestClient(make_app(database_path)) as first_client:
        created = create_profile(first_client)

    with TestClient(make_app(database_path)) as restarted_client:
        fetched = restarted_client.get(f"/api/steering/profiles/{created['profile_id']}")

    assert fetched.status_code == 200
    assert fetched.json() == created


@pytest.mark.parametrize(
    "payload",
    [
        profile_payload(" Track "),
        {**profile_payload(), "definition": {**definition_json(), "schema_version": 2}},
        {**profile_payload(), "definition": {**definition_json(), "unexpected": "value"}},
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
        "message": (f"steering profile {created['profile_id']} is at revision 2, not 1"),
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
    activate_simulation_devices(client.app.state.controller_service)
    initial_curve = client.app.state.controller_service.snapshot().application.active_steering_curve
    applied_definition = definition_json(second_assistance=850)

    applied = client.put(
        "/api/commands/steering-curve",
        json={"definition": applied_definition},
    )
    active_after_apply = client.app.state.controller_service.snapshot().application
    catalog_after_apply = client.get("/api/steering/profiles").json()
    saved = create_profile(client, "Saved only")
    curve_after_save = client.app.state.controller_service.snapshot().application

    assert applied.status_code == 200
    assert applied.json()["accepted"] is True
    assert (
        definition_primitive(active_after_apply.active_steering_curve.definition)
        == applied_definition
    )
    assert (
        active_after_apply.active_steering_curve.activation_revision
        == initial_curve.activation_revision + 1
    )
    assert active_after_apply.active_steering_curve.saved_profile_id is None
    assert len(catalog_after_apply) == 1
    assert saved["definition"] == applied_definition
    assert curve_after_save.active_steering_curve == active_after_apply.active_steering_curve


def test_stale_saved_profile_activation_is_rejected(client: TestClient) -> None:
    saved = create_profile(client)
    before = client.app.state.controller_service.snapshot().application

    response = client.post(
        "/api/commands/activate-steering-profile",
        json={"profile_id": saved["profile_id"], "expected_revision": 99},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "profile_revision_conflict"
    assert response.json()["error"]["current_revision"] == 1
    assert client.app.state.controller_service.snapshot().application == before


def test_matching_saved_profile_is_activated(client: TestClient) -> None:
    activate_simulation_devices(client.app.state.controller_service)
    saved = create_profile(client)

    response = client.post(
        "/api/commands/activate-steering-profile",
        json={
            "profile_id": saved["profile_id"],
            "expected_revision": saved["revision"],
        },
    )
    active = client.app.state.controller_service.snapshot().application.active_steering_curve

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert active.saved_profile_id == saved["profile_id"]
    assert active.saved_profile_revision == 1


def test_saved_profile_command_rejects_unknown_fields(client: TestClient) -> None:
    response = client.post(
        "/api/commands/activate-steering-profile",
        json={
            "profile_id": "11111111-1111-4111-8111-111111111111",
            "expected_revision": 1,
            "definition": definition_json(),
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


class BlockingShutdownPeer(SimulatedServotronicPeer):
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


def test_activation_queue_overload_is_bounded(tmp_path: Path) -> None:
    config = replace(
        simulator_config(),
        simulation=SimulationConfig(),
        tick_interval_s=60.0,
        runtime_inbox_capacity=1,
    )
    controllers: list[BlockingShutdownPeer] = []

    def build_controller(
        watchdog_timeout_s: float,
        clock: Callable[[], float],
    ) -> BlockingShutdownPeer:
        controller = BlockingShutdownPeer(
            watchdog_timeout_s,
            clock,
            block_shutdown=not controllers,
        )
        controllers.append(controller)
        return controller

    app = make_app(
        tmp_path / "profiles.sqlite3",
        config=config,
        servotronic_factory=build_controller,
    )

    with TestClient(app) as client:
        activate_simulation_devices(app.state.controller_service)
        with ThreadPoolExecutor(max_workers=3) as pool:
            first = pool.submit(
                client.post,
                "/api/dev/simulation/reset",
            )
            controller = controllers[0]
            assert controller.entered.wait(timeout=1.0)
            second = pool.submit(
                client.post,
                "/api/dev/simulation/devices/button-pad/buttons/0/tap",
            )
            deadline = time.monotonic() + 1.0
            while app.state.controller_service.inbox_depth != 1 and time.monotonic() < deadline:
                pass
            assert app.state.controller_service.inbox_depth == 1
            overloaded = pool.submit(
                client.put,
                "/api/commands/steering-curve",
                json={"definition": definition_json(second_assistance=850)},
            )
            try:
                overloaded_response = overloaded.result(timeout=1.0)
            finally:
                controller.release.set()
            assert first.result().status_code == 200
            assert second.result().status_code == 503

    assert overloaded_response.status_code == 503
    assert overloaded_response.json()["error"]["code"] == "runtime_queue_full"


class RejectingActivationPeer(SimulatedServotronicPeer):
    def __init__(self, watchdog_timeout_s: float, clock: Callable[[], float]) -> None:
        super().__init__(watchdog_timeout_s, clock)
        self.auto_commands = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        if command.reason is SteeringCommandReason.AUTO:
            self.auto_commands += 1
            if self.auto_commands == 1:
                raise OSError("activation effect rejected")
        super().set_assistance(command)


def test_save_then_failed_activation_records_nonfatal_adapter_fault(tmp_path: Path) -> None:
    config = replace(simulator_config(), tick_interval_s=60.0)
    app = make_app(
        tmp_path / "profiles.sqlite3",
        config=config,
        servotronic_factory=RejectingActivationPeer,
    )

    with TestClient(app) as client:
        activate_simulation_devices(app.state.controller_service)
        saved = create_profile(client)
        speed = client.put("/api/dev/simulation/vehicle/speed", json={"speed_kph": 10.0})
        assert speed.status_code == 200
        before = app.state.controller_service.snapshot()
        activation = client.post(
            "/api/commands/activate-steering-profile",
            json={
                "profile_id": saved["profile_id"],
                "expected_revision": saved["revision"],
            },
        )
        fetched = client.get(f"/api/steering/profiles/{saved['profile_id']}")
        runtime_snapshot = app.state.controller_service.snapshot()

    assert before.diagnostics.health.fatal is False
    assert activation.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json() == saved
    assert runtime_snapshot.diagnostics.health.fatal is False
    assert runtime_snapshot.diagnostics.health.steering_actuator_fault is not None
    assert (
        definition_primitive(runtime_snapshot.application.active_steering_curve.definition)
        == saved["definition"]
    )
    assert (
        runtime_snapshot.application.active_steering_curve.saved_profile_id == saved["profile_id"]
    )


def test_runtime_snapshot_and_profile_resource_remain_authoritative(
    client: TestClient,
) -> None:
    activate_simulation_devices(client.app.state.controller_service)
    applied_definition = definition_json(second_assistance=850)
    applied = client.put(
        "/api/commands/steering-curve",
        json={"definition": applied_definition},
    )
    assert applied.status_code == 200

    snapshot = client.app.state.controller_service.snapshot()
    created = client.post("/api/steering/profiles", json=profile_payload())

    assert (
        definition_primitive(snapshot.application.active_steering_curve.definition)
        == applied_definition
    )
    assert created.status_code == 201
