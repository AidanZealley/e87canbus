from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from typing import Any, cast, get_args

import pytest
from e87canbus.api.internal.button_profiles import definition_from_request
from e87canbus.api.main import create_app
from e87canbus.api.models.button_profiles import (
    ButtonProfileCommand,
    ButtonProfileDefinitionRequest,
)
from e87canbus.config import simulator_config
from e87canbus.domain.button_profiles import UserButtonIntent, encode_button_intent
from e87canbus.domain.revisioned_profiles import ProfileStorageError
from fastapi import FastAPI
from fastapi.testclient import TestClient


def definition_json() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "slots": [
            {"type": "select_steering_mode", "mode": "auto"},
            {"type": "toggle_automatic_assistance"},
            {"type": "adjust_manual_assistance", "delta": -1},
            {"type": "set_manual_assistance_level", "level": 3},
            {"type": "set_maximum_assistance", "enabled": True},
            {"type": "toggle_maximum_assistance"},
            {"type": "start_high_beam_strobe"},
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ],
    }


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        config=simulator_config(),
        profile_database_path=tmp_path / "button-profiles.sqlite3",
    )
    with TestClient(app) as test_client:
        yield test_client


def test_button_profile_crud_and_saved_convenience_resource(client: TestClient) -> None:
    initial = client.get("/api/button-pad/profile")
    created = client.post("/api/button-pad/profiles", json={"name": "Track"})

    assert initial.status_code == 200
    assert len(initial.json()["definition"]["slots"]) == 16
    assert created.status_code == 201
    assert created.json()["definition"] == {"schema_version": 1, "slots": [None] * 16}

    profile_id = created.json()["profile_id"]
    fetched = client.get(f"/api/button-pad/profiles/{profile_id}")
    updated = client.put(
        f"/api/button-pad/profiles/{profile_id}",
        json={
            "name": "Track controls",
            "expected_revision": 1,
            "definition": definition_json(),
        },
    )

    assert fetched.json() == created.json()
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["definition"] == definition_json()
    assert len(client.get("/api/button-pad/profiles").json()) == 2
    assert (
        client.delete(
            f"/api/button-pad/profiles/{profile_id}", params={"expected_revision": 2}
        ).status_code
        == 204
    )
    assert client.get(f"/api/button-pad/profiles/{profile_id}").status_code == 404


def test_saved_button_profile_is_directly_editable(client: TestClient) -> None:
    saved = client.get("/api/button-pad/profile").json()
    updated = client.put(
        f"/api/button-pad/profiles/{saved['profile_id']}",
        json={
            "name": saved["name"],
            "expected_revision": saved["revision"],
            "definition": definition_json(),
        },
    )

    assert updated.status_code == 200
    assert client.get("/api/button-pad/profile").json() == updated.json()


def test_activation_compiles_saved_revision_and_projects_live_identity(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/button-pad/profiles",
        json={"name": "Active", "definition": definition_json()},
    ).json()
    activated = client.post(
        "/api/button-pad/activate-profile",
        json={"profile_id": created["profile_id"], "expected_revision": 1},
    )
    app = cast(FastAPI, client.app)
    snapshot = app.state.controller_service.snapshot()

    assert activated.status_code == 200
    assert set(activated.json()) == {"accepted", "boot_id", "revision"}
    assert snapshot.application.active_button_profile_id == created["profile_id"]
    assert snapshot.application.active_button_profile_revision == 1
    assert snapshot.application.button_pad_program.payloads


def test_activation_publishes_selected_profile_resource_change(client: TestClient) -> None:
    events: list[Any] = []
    cast(FastAPI, client.app).state.live_publisher.offer_resource = events.append
    created = client.post("/api/button-pad/profiles", json={"name": "Published"}).json()
    events.clear()

    response = client.post(
        "/api/button-pad/activate-profile",
        json={"profile_id": created["profile_id"], "expected_revision": 1},
    )

    assert response.status_code == 200
    assert [event.model_dump() for event in events] == [
        {
            "type": "resources.changed",
            "resource": "button_profile",
            "id": created["profile_id"],
            "revision": 1,
        }
    ]


def test_activation_storage_failure_keeps_runtime_and_marks_persistence_unhealthy(
    client: TestClient,
) -> None:
    app = cast(FastAPI, client.app)
    previous = client.get("/api/button-pad/profile").json()
    created = client.post("/api/button-pad/profiles", json={"name": "Runtime only"}).json()

    def fail_selection(_profile_id: str, _revision: int) -> None:
        raise ProfileStorageError("selection write failed")

    app.state.button_profile_repository.select_profile = fail_selection
    response = client.post(
        "/api/button-pad/activate-profile",
        json={"profile_id": created["profile_id"], "expected_revision": 1},
    )
    snapshot = app.state.controller_service.snapshot()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "profile_storage_error"
    assert snapshot.application.active_button_profile_id == created["profile_id"]
    assert snapshot.application.active_button_profile_revision == 1
    assert snapshot.service.persistence.available is False
    assert snapshot.service.persistence.fault == "selection write failed"
    assert client.get("/api/button-pad/profile").json() == previous


def test_concurrent_activations_leave_runtime_and_durable_selection_aligned(
    client: TestClient,
) -> None:
    profiles = [
        client.post("/api/button-pad/profiles", json={"name": name}).json()
        for name in ("Concurrent A", "Concurrent B")
    ]

    def activate(profile: dict[str, Any]) -> int:
        return client.post(
            "/api/button-pad/activate-profile",
            json={"profile_id": profile["profile_id"], "expected_revision": 1},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = tuple(pool.map(activate, profiles))

    app = cast(FastAPI, client.app)
    runtime_id = app.state.controller_service.snapshot().application.active_button_profile_id
    durable_id = client.get("/api/button-pad/profile").json()["profile_id"]
    assert statuses == (200, 200)
    assert runtime_id == durable_id


def test_update_wins_race_before_activation_cannot_activate_stale_revision(
    client: TestClient,
) -> None:
    app = cast(FastAPI, client.app)
    repository = app.state.button_profile_repository
    created = client.post("/api/button-pad/profiles", json={"name": "Update race"}).json()
    update_entered, release_update = Event(), Event()
    original_update = repository.update_profile

    def paused_update(*args: Any, **kwargs: Any) -> Any:
        update_entered.set()
        assert release_update.wait(2)
        return original_update(*args, **kwargs)

    repository.update_profile = paused_update
    update_body = {
        "name": "Updated first",
        "expected_revision": 1,
        "definition": definition_json(),
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        update_future = pool.submit(
            client.put,
            f"/api/button-pad/profiles/{created['profile_id']}",
            json=update_body,
        )
        assert update_entered.wait(2)
        activation_future = pool.submit(
            client.post,
            "/api/button-pad/activate-profile",
            json={"profile_id": created["profile_id"], "expected_revision": 1},
        )
        release_update.set()
        update = update_future.result()
        activation = activation_future.result()

    snapshot = app.state.controller_service.snapshot()
    assert update.status_code == 200
    assert activation.status_code == 409
    assert activation.json()["error"]["current_revision"] == 2
    assert snapshot.application.active_button_profile_id != created["profile_id"]


def test_delete_wins_race_before_activation_cannot_activate_deleted_profile(
    client: TestClient,
) -> None:
    app = cast(FastAPI, client.app)
    repository = app.state.button_profile_repository
    created = client.post("/api/button-pad/profiles", json={"name": "Delete race"}).json()
    delete_entered, release_delete = Event(), Event()
    original_delete = repository.delete_profile

    def paused_delete(*args: Any, **kwargs: Any) -> Any:
        delete_entered.set()
        assert release_delete.wait(2)
        return original_delete(*args, **kwargs)

    repository.delete_profile = paused_delete
    with ThreadPoolExecutor(max_workers=2) as pool:
        delete_future = pool.submit(
            client.delete,
            f"/api/button-pad/profiles/{created['profile_id']}",
            params={"expected_revision": 1},
        )
        assert delete_entered.wait(2)
        activation_future = pool.submit(
            client.post,
            "/api/button-pad/activate-profile",
            json={"profile_id": created["profile_id"], "expected_revision": 1},
        )
        release_delete.set()
        deleted = delete_future.result()
        activation = activation_future.result()

    snapshot = app.state.controller_service.snapshot()
    assert deleted.status_code == 204
    assert activation.status_code == 404
    assert snapshot.application.active_button_profile_id != created["profile_id"]


def test_activation_checks_the_exact_saved_revision(client: TestClient) -> None:
    saved = client.get("/api/button-pad/profile").json()
    conflict = client.post(
        "/api/button-pad/activate-profile",
        json={"profile_id": saved["profile_id"], "expected_revision": saved["revision"] + 1},
    )
    missing = client.post(
        "/api/button-pad/activate-profile",
        json={
            "profile_id": "00000000-0000-4000-8000-000000000099",
            "expected_revision": 1,
        },
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["current_revision"] == saved["revision"]
    assert missing.status_code == 404


def test_activation_selection_survives_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "button-profiles.sqlite3"
    first_app = create_app(config=simulator_config(), profile_database_path=database_path)
    with TestClient(first_app) as first:
        created = first.post(
            "/api/button-pad/profiles",
            json={"name": "Persistent active", "definition": definition_json()},
        ).json()
        assert (
            first.post(
                "/api/button-pad/activate-profile",
                json={"profile_id": created["profile_id"], "expected_revision": 1},
            ).status_code
            == 200
        )
        assert first.get("/api/button-pad/profile").json() == created

    second_app = create_app(config=simulator_config(), profile_database_path=database_path)
    with TestClient(second_app) as second:
        snapshot = cast(FastAPI, second.app).state.controller_service.snapshot()
        assert second.get("/api/button-pad/profile").json() == created
        assert snapshot.application.active_button_profile_id == created["profile_id"]
        assert snapshot.application.active_button_profile_revision == 1


def test_selected_and_built_in_profiles_cannot_be_deleted(client: TestClient) -> None:
    built_in = client.get("/api/button-pad/profile").json()
    built_in_delete = client.delete(
        f"/api/button-pad/profiles/{built_in['profile_id']}",
        params={"expected_revision": built_in["revision"]},
    )
    created = client.post("/api/button-pad/profiles", json={"name": "Selected"}).json()
    client.post(
        "/api/button-pad/activate-profile",
        json={"profile_id": created["profile_id"], "expected_revision": 1},
    )
    selected_delete = client.delete(
        f"/api/button-pad/profiles/{created['profile_id']}",
        params={"expected_revision": 1},
    )

    assert built_in_delete.status_code == 409
    assert built_in_delete.json()["error"]["code"] == "profile_protected"
    assert selected_delete.status_code == 409
    assert selected_delete.json()["error"]["code"] == "profile_protected"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["slots"].pop(),
        lambda value: value["slots"].append(None),
        lambda value: value["slots"].__setitem__(
            0, {"type": "adjust_manual_assistance", "delta": 2}
        ),
        lambda value: value["slots"].__setitem__(0, {"type": "not_a_command"}),
        lambda value: value["slots"].__setitem__(
            0, {"type": "toggle_maximum_assistance", "extra": True}
        ),
    ],
)
def test_profile_definition_contract_rejects_ambiguous_or_invalid_slots(
    client: TestClient, mutate: Callable[[dict[str, Any]], object]
) -> None:
    definition = definition_json()
    mutate(definition)
    response = client.post(
        "/api/button-pad/profiles",
        json={"name": "Invalid", "definition": definition},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_button_profile_revision_conflicts_are_authoritative(client: TestClient) -> None:
    saved = client.get("/api/button-pad/profile").json()
    first = client.put(
        f"/api/button-pad/profiles/{saved['profile_id']}",
        json={
            "name": saved["name"],
            "expected_revision": saved["revision"],
            "definition": definition_json(),
        },
    )
    stale = client.put(
        f"/api/button-pad/profiles/{saved['profile_id']}",
        json={
            "name": saved["name"],
            "expected_revision": saved["revision"],
            "definition": definition_json(),
        },
    )

    assert first.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["error"]["current_revision"] == first.json()["revision"]


def test_one_command_vocabulary_is_shared_by_http_and_storage() -> None:
    """Adding an eighth button command must break here rather than silently half-land.

    The HTTP request models, the domain codec and the response encoder must agree on the
    same tag set, so this pins the three together instead of trusting them to drift apart.
    """

    http_tags = {
        get_args(member.model_fields["type"].annotation)[0]
        for member in get_args(get_args(ButtonProfileCommand)[0])
    }
    samples = [slot for slot in definition_json()["slots"] if slot is not None]

    assert http_tags == {sample["type"] for sample in samples}
    assert len(http_tags) == len(get_args(UserButtonIntent))
    # Every tag survives the round trip HTTP model -> domain intent -> stored JSON.
    definition = definition_from_request(
        ButtonProfileDefinitionRequest.model_validate(definition_json())
    )
    assert [
        encode_button_intent(intent) for intent in definition.slots if intent is not None
    ] == samples
    assert {type(intent) for intent in definition.slots if intent is not None} == set(
        get_args(UserButtonIntent)
    )
