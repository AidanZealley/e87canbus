from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from e87canbus.api.internal.button_profiles import definition_from_request
from e87canbus.api.main import create_app
from e87canbus.api.models.button_profiles import (
    ButtonProfileCommand,
    ButtonProfileDefinitionRequest,
)
from e87canbus.config import simulator_config
from e87canbus.domain.buttons.catalogue import ButtonCommand
from e87canbus.domain.buttons.profiles import encode_button_slot
from e87canbus.domain.revisioned_profiles import ProfileStorageError
from fastapi import FastAPI
from fastapi.testclient import TestClient


def slot_json(
    command: dict[str, Any],
    colour: list[int] | None = None,
    animation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "command": command,
        "colour": colour or [255, 255, 255],
        "active_colour": None,
        "animation": animation,
    }


def definition_json() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "slots": [
            slot_json({"type": "select_steering_mode", "mode": "auto"}, [0, 0, 255]),
            slot_json(
                {"type": "toggle_automatic_assistance"},
                [0, 0, 255],
                {"kind": "breathe", "period_ms": 2000, "minimum": 8, "maximum": 255},
            ),
            slot_json({"type": "adjust_manual_assistance", "delta": -1}),
            slot_json({"type": "set_manual_assistance_level", "level": 3}),
            slot_json(
                {"type": "set_maximum_assistance", "enabled": True},
                [255, 0, 0],
                {"kind": "blink", "on_ms": 400, "off_ms": 400},
            ),
            slot_json({"type": "toggle_maximum_assistance"}),
            slot_json({"type": "start_high_beam_strobe"}),
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
    assert created.json()["definition"] == {"schema_version": 2, "slots": [None] * 16}

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


def test_update_installs_saved_revision_and_projects_live_identity(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/button-pad/profiles",
        json={"name": "Active", "definition": definition_json()},
    ).json()
    updated = client.put(
        f"/api/button-pad/profiles/{created['profile_id']}",
        json={
            "name": created["name"],
            "expected_revision": 1,
            "definition": definition_json(),
        },
    )
    app = cast(FastAPI, client.app)
    snapshot = app.state.controller_loop.snapshot()

    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert snapshot.application.active_button_profile_id == created["profile_id"]
    assert snapshot.application.active_button_profile_revision == 2
    assert snapshot.application.button_pad_program.payloads
    assert client.get("/api/button-pad/profile").json() == updated.json()


def test_update_publishes_selected_profile_resource_change(client: TestClient) -> None:
    events: list[Any] = []
    cast(FastAPI, client.app).state.live_publisher.offer_resource = events.append
    created = client.post("/api/button-pad/profiles", json={"name": "Published"}).json()
    events.clear()

    response = client.put(
        f"/api/button-pad/profiles/{created['profile_id']}",
        json={
            "name": created["name"],
            "expected_revision": 1,
            "definition": definition_json(),
        },
    )

    assert response.status_code == 200
    assert [event.model_dump() for event in events] == [
        {
            "type": "resources.changed",
            "resource": "button_profile",
            "id": created["profile_id"],
            "revision": 2,
        }
    ]


def test_update_selection_failure_keeps_runtime_and_marks_persistence_unhealthy(
    client: TestClient,
) -> None:
    app = cast(FastAPI, client.app)
    previous = client.get("/api/button-pad/profile").json()
    created = client.post("/api/button-pad/profiles", json={"name": "Runtime only"}).json()

    def fail_selection(_profile_id: str, _revision: int) -> None:
        raise ProfileStorageError("selection write failed")

    app.state.button_profile_repository.select_profile = fail_selection
    response = client.put(
        f"/api/button-pad/profiles/{created['profile_id']}",
        json={
            "name": created["name"],
            "expected_revision": 1,
            "definition": definition_json(),
        },
    )
    snapshot = app.state.controller_loop.snapshot()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "profile_storage_error"
    assert snapshot.application.active_button_profile_id == created["profile_id"]
    assert snapshot.application.active_button_profile_revision == 2
    assert snapshot.service.persistence.available is False
    assert snapshot.service.persistence.fault == "selection write failed"
    assert client.get("/api/button-pad/profile").json() == previous


def test_updated_selection_survives_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "button-profiles.sqlite3"
    first_app = create_app(config=simulator_config(), profile_database_path=database_path)
    with TestClient(first_app) as first:
        created = first.post(
            "/api/button-pad/profiles",
            json={"name": "Persistent active", "definition": definition_json()},
        ).json()
        updated = first.put(
            f"/api/button-pad/profiles/{created['profile_id']}",
            json={
                "name": created["name"],
                "expected_revision": 1,
                "definition": definition_json(),
            },
        )
        assert updated.status_code == 200
        assert first.get("/api/button-pad/profile").json() == updated.json()

    second_app = create_app(config=simulator_config(), profile_database_path=database_path)
    with TestClient(second_app) as second:
        snapshot = cast(FastAPI, second.app).state.controller_loop.snapshot()
        assert second.get("/api/button-pad/profile").json() == updated.json()
        assert snapshot.application.active_button_profile_id == created["profile_id"]
        assert snapshot.application.active_button_profile_revision == 2


def test_selected_and_built_in_profiles_cannot_be_deleted(client: TestClient) -> None:
    built_in = client.get("/api/button-pad/profile").json()
    built_in_delete = client.delete(
        f"/api/button-pad/profiles/{built_in['profile_id']}",
        params={"expected_revision": built_in["revision"]},
    )
    created = client.post("/api/button-pad/profiles", json={"name": "Selected"}).json()
    updated = client.put(
        f"/api/button-pad/profiles/{created['profile_id']}",
        json={
            "name": created["name"],
            "expected_revision": 1,
            "definition": definition_json(),
        },
    )
    selected_delete = client.delete(
        f"/api/button-pad/profiles/{created['profile_id']}",
        params={"expected_revision": updated.json()["revision"]},
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
            0, slot_json({"type": "adjust_manual_assistance", "delta": 2})
        ),
        lambda value: value["slots"].__setitem__(0, slot_json({"type": "not_a_command"})),
        lambda value: value["slots"].__setitem__(
            0, slot_json({"type": "toggle_maximum_assistance", "extra": True})
        ),
        # A slot is the command plus its presentation; the bare command is v1's shape.
        lambda value: value["slots"].__setitem__(0, {"type": "toggle_maximum_assistance"}),
        # An out-of-range colour channel, and a colour that is not a triple at all.
        lambda value: value["slots"][0].__setitem__("colour", [0, 0, 256]),
        lambda value: value["slots"][0].__setitem__("colour", [-1, 0, 0]),
        lambda value: value["slots"][0].__setitem__("colour", [0, 0]),
        # active_colour is reserved until a renderer honours it.
        lambda value: value["slots"][0].__setitem__("active_colour", [255, 0, 0]),
        # Breathe bounds, both ends of the period and the brightness ordering.
        lambda value: value["slots"][1]["animation"].__setitem__("period_ms", 249),
        lambda value: value["slots"][1]["animation"].__setitem__("period_ms", 10_001),
        lambda value: value["slots"][1]["animation"].update({"minimum": 200, "maximum": 199}),
        lambda value: value["slots"][1]["animation"].__setitem__("maximum", 256),
        # Blink bounds, both ends of both durations.
        lambda value: value["slots"][4]["animation"].__setitem__("on_ms", 0),
        lambda value: value["slots"][4]["animation"].__setitem__("off_ms", 10_001),
        lambda value: value["slots"][1]["animation"].__setitem__("kind", "sparkle"),
        # Animation on a command that has no active state to animate.
        lambda value: value["slots"][6].__setitem__(
            "animation", {"kind": "blink", "on_ms": 400, "off_ms": 400}
        ),
        lambda value: value["slots"][2].__setitem__(
            "animation", {"kind": "breathe", "period_ms": 2000, "minimum": 8, "maximum": 255}
        ),
        # The API accepts one schema version: a v1 body is rejected, not upgraded.
        lambda value: value.__setitem__("schema_version", 1),
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


@pytest.mark.parametrize(
    "slot",
    [
        slot_json({"type": "toggle_maximum_assistance"}, [0, 0, 0]),
        slot_json({"type": "toggle_maximum_assistance"}, [255, 255, 255]),
        slot_json(
            {"type": "toggle_maximum_assistance"},
            None,
            {"kind": "breathe", "period_ms": 250, "minimum": 0, "maximum": 0},
        ),
        slot_json(
            {"type": "toggle_maximum_assistance"},
            None,
            {"kind": "breathe", "period_ms": 10_000, "minimum": 255, "maximum": 255},
        ),
        slot_json(
            {"type": "toggle_maximum_assistance"},
            None,
            {"kind": "breathe", "period_ms": 2000, "minimum": 200, "maximum": 200},
        ),
        slot_json(
            {"type": "toggle_maximum_assistance"},
            None,
            {"kind": "blink", "on_ms": 1, "off_ms": 1},
        ),
        slot_json(
            {"type": "toggle_maximum_assistance"},
            None,
            {"kind": "blink", "on_ms": 10_000, "off_ms": 10_000},
        ),
    ],
)
def test_a_slot_exactly_on_its_bounds_is_accepted(client: TestClient, slot: dict[str, Any]) -> None:
    """The rejections above would also pass if the accepted range were one step too tight."""

    definition = definition_json()
    definition["slots"][0] = slot

    response = client.post(
        "/api/button-pad/profiles",
        json={"name": "On the boundary", "definition": definition},
    )

    assert response.status_code == 201
    assert response.json()["definition"]["slots"][0] == slot


def test_a_whole_v1_definition_body_is_rejected_rather_than_upgraded(client: TestClient) -> None:
    """Migration is a property of stored rows; over HTTP there is one accepted shape."""

    v1_definition = {
        "schema_version": 1,
        "slots": [{"type": "toggle_automatic_assistance"}] + [None] * 15,
    }

    response = client.post(
        "/api/button-pad/profiles",
        json={"name": "Legacy", "definition": v1_definition},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_authored_colour_and_animation_round_trip_through_http_and_storage(
    client: TestClient,
) -> None:
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
    stored = client.get(f"/api/button-pad/profiles/{saved['profile_id']}").json()
    assert stored["definition"] == definition_json()
    assert stored["definition"]["slots"][1]["animation"] == {
        "kind": "breathe",
        "period_ms": 2000,
        "minimum": 8,
        "maximum": 255,
    }
    assert stored["definition"]["slots"][4]["colour"] == [255, 0, 0]


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

    The HTTP request models are generated from the catalogue, so their tags agree with
    storage by construction. What this still pins is the hand-written sample payload
    above: a new catalogue entry that nothing exercises over HTTP fails here, and the
    round trip proves the generated model, the domain codec and the response encoder
    all speak the same tag.
    """

    http_tags = {
        get_args(member.model_fields["type"].annotation)[0]
        for member in get_args(get_args(ButtonProfileCommand)[0])
    }
    samples = [slot for slot in definition_json()["slots"] if slot is not None]

    assert http_tags == {sample["command"]["type"] for sample in samples}
    assert len(http_tags) == len(get_args(ButtonCommand))
    # Every tag survives the round trip HTTP model -> domain slot -> stored JSON.
    definition = definition_from_request(
        ButtonProfileDefinitionRequest.model_validate(definition_json()),
        simulator_config().steering,
    )
    assert [encode_button_slot(slot) for slot in definition.slots if slot is not None] == samples
    assert {type(slot.command) for slot in definition.slots if slot is not None} == set(
        get_args(ButtonCommand)
    )


def test_assistance_level_beyond_the_configured_stages_is_rejected(client: TestClient) -> None:
    """A schema-valid level the vehicle cannot select must fail at save, not on press."""

    definition = definition_json()
    stage_count = simulator_config().steering.manual_level_count
    definition["slots"][3] = slot_json(
        {"type": "set_manual_assistance_level", "level": stage_count}
    )

    response = client.post(
        "/api/button-pad/profiles",
        json={"name": "Out of range", "definition": definition},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (
        f"button 3: manual assistance level must be between 0 and {stage_count - 1}"
        in (response.json()["error"]["message"])
    )
