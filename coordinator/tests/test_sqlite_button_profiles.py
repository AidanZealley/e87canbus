import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from e87canbus.adapters.sqlite_button_profiles import SqliteButtonProfileRepository
from e87canbus.adapters.sqlite_database import (
    BUILT_IN_BUTTON_PROFILE_ID,
    BUILT_IN_BUTTON_PROFILE_NAME,
    CURRENT_MIGRATION_VERSION,
    SqliteApplicationDatabase,
)
from e87canbus.domain.buttons.profiles import (
    BUILT_IN_BUTTON_PROFILE,
    ButtonProfileDefinition,
    canonical_button_profile_bytes,
    decode_button_profile,
    empty_button_profile_definition,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.revisioned_profiles import (
    ProfileNameConflictError,
    ProfileProtectedError,
    ProfileRevisionConflictError,
    StoredProfileDataError,
)
from e87canbus.domain.state import SteeringMode

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)
IDENTIFIER = UUID("12345678-1234-4678-9234-567812345678")


def repository(path: Path) -> SqliteButtonProfileRepository:
    return SqliteButtonProfileRepository(
        path, clock=lambda: NOW, identifier_factory=lambda: IDENTIFIER
    )


def test_migration_seeds_editable_current_mapping_and_is_idempotent(tmp_path: Path) -> None:
    repo = repository(tmp_path / "app.sqlite")
    repo.initialize()
    repo.initialize()
    seed = repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)
    assert seed is not None
    assert seed.name == BUILT_IN_BUTTON_PROFILE_NAME
    assert seed.definition == BUILT_IN_BUTTON_PROFILE
    assert seed.definition.slots[15] is None  # development breathe action is deliberately omitted
    renamed = repo.update_profile(seed.profile_id, 1, "My buttons", seed.definition)
    repo.initialize()
    assert repo.get_profile(seed.profile_id) == renamed
    with sqlite3.connect(tmp_path / "app.sqlite") as connection:
        assert (
            connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
            == CURRENT_MIGRATION_VERSION
        )


def test_v6_upgrade_selects_first_profile_when_builtin_is_absent(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    created = repo.create_profile("Only remaining")
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DROP TABLE selected_button_profile")
        connection.execute("DELETE FROM schema_migrations WHERE version=7")
        connection.execute(
            "DELETE FROM button_profiles WHERE profile_id=?",
            (BUILT_IN_BUTTON_PROFILE_ID,),
        )
    repo.initialize()

    assert repo.get_selected_profile() == created


def test_create_defaults_to_explicit_complete_inert_pad_and_crud(tmp_path: Path) -> None:
    repo = repository(tmp_path / "app.sqlite")
    repo.initialize()
    created = repo.create_profile("Empty")
    assert created.definition == empty_button_profile_definition()
    assert len(created.definition.slots) == 16 and set(created.definition.slots) == {None}
    changed = replace(created.definition, slots=(ToggleMaximumAssistance(),) + (None,) * 15)
    updated = repo.update_profile(created.profile_id, 1, "Edited", changed)
    assert updated.revision == 2 and repo.get_profile(created.profile_id) == updated
    repo.delete_profile(created.profile_id, 2)
    assert repo.get_profile(created.profile_id) is None


def test_selected_profile_is_durable_and_cannot_be_deleted(tmp_path: Path) -> None:
    repo = repository(tmp_path / "app.sqlite")
    repo.initialize()
    created = repo.create_profile("Selected")
    assert repo.get_selected_profile().profile_id == BUILT_IN_BUTTON_PROFILE_ID
    assert repo.select_profile(created.profile_id, created.revision) == created
    assert repo.get_selected_profile() == created
    with pytest.raises(ProfileProtectedError, match="selected"):
        repo.delete_profile(created.profile_id, created.revision)
    with pytest.raises(ProfileProtectedError, match="built-in"):
        repo.delete_profile(BUILT_IN_BUTTON_PROFILE_ID, 1)


def test_optimistic_revision_and_case_insensitive_names(tmp_path: Path) -> None:
    repo = repository(tmp_path / "app.sqlite")
    repo.initialize()
    created = repo.create_profile("Track")
    repo.update_profile(created.profile_id, 1, "Track", created.definition)
    with pytest.raises(ProfileRevisionConflictError):
        repo.update_profile(created.profile_id, 1, "Track", created.definition)
    with pytest.raises(ProfileNameConflictError):
        repo.create_profile("track")


def test_codec_round_trips_every_user_command_and_rejects_foreign_command() -> None:
    commands = (
        SelectSteeringMode(SteeringMode.AUTO),
        ToggleAutomaticAssistance(),
        AdjustManualAssistance(-1),
        SetManualAssistanceLevel(3),
        SetMaximumAssistance(True),
        ToggleMaximumAssistance(),
        StartHighBeamStrobe(),
    )
    definition = ButtonProfileDefinition(1, commands + (None,) * 9)
    assert (
        decode_button_profile(json.loads(canonical_button_profile_bytes(definition))) == definition
    )
    with pytest.raises(ValueError, match="not user-bindable"):
        ButtonProfileDefinition(1, ("toggle_automatic_assistance",) + (None,) * 15)  # type: ignore[arg-type]
    raw = {"schema_version": 1, "slots": [{"type": "toggle_button_pad_lamp_test"}] + [None] * 15}
    with pytest.raises(ValueError, match="unsupported"):
        decode_button_profile(raw)
    with pytest.raises(ValueError, match="must be an integer"):
        ButtonProfileDefinition(True, (None,) * 16)


def test_corrupt_noncanonical_storage_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE button_profiles SET definition_json=? WHERE profile_id=?",
            ('{"slots":[],"schema_version":1}', BUILT_IN_BUTTON_PROFILE_ID),
        )
    with pytest.raises(StoredProfileDataError):
        repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)


def _is_closed(connection: sqlite3.Connection) -> bool:
    try:
        connection.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


def test_every_operation_closes_its_connection_even_when_it_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed call must not leave a WAL reader alive for as long as its traceback does.

    ``sqlite3``'s connection context manager only ends the transaction, so this is the
    regression guard for the adapter closing in ``finally`` instead.
    """

    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    other = repo.create_profile("Track")

    opened: list[sqlite3.Connection] = []
    connect = SqliteApplicationDatabase.connect

    def tracked(self: SqliteApplicationDatabase) -> sqlite3.Connection:
        connection = connect(self)
        opened.append(connection)
        return connection

    monkeypatch.setattr(SqliteApplicationDatabase, "connect", tracked)
    with sqlite3.connect(path) as raw:
        raw.execute("UPDATE button_profiles SET definition_fingerprint=?", ("0" * 64,))

    failures: list[Callable[[], object]] = [
        lambda: repo.list_profiles(),
        lambda: repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID),
        lambda: repo.get_selected_profile(),
        lambda: repo.select_profile(BUILT_IN_BUTTON_PROFILE_ID, 99),
        lambda: repo.create_profile("Track"),
        lambda: repo.update_profile(other.profile_id, 99, "Rally", other.definition),
        lambda: repo.delete_profile(BUILT_IN_BUTTON_PROFILE_ID, 1),
    ]
    for failing in failures:
        with pytest.raises(Exception):  # noqa: B017 - the failure kind differs per call
            failing()

    assert len(opened) == len(failures)
    assert all(_is_closed(connection) for connection in opened)
