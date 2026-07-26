import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
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
    BlinkAnimation,
    BreatheAnimation,
    ButtonProfileDefinition,
    ButtonSlot,
    SlotAnimation,
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
from e87canbus.domain.state import RGB_BLUE, RGB_WHITE, Rgb, SteeringMode

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
    changed = replace(
        created.definition,
        slots=(ButtonSlot(ToggleMaximumAssistance(), RGB_BLUE),) + (None,) * 15,
    )
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
    slots = (
        ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), RGB_BLUE),
        ButtonSlot(ToggleAutomaticAssistance(), RGB_BLUE, animation=BlinkAnimation(400, 400)),
        ButtonSlot(AdjustManualAssistance(-1), RGB_WHITE),
        ButtonSlot(SetManualAssistanceLevel(3), (1, 2, 3)),
        ButtonSlot(SetMaximumAssistance(True), RGB_WHITE, animation=BreatheAnimation(2000, 8, 255)),
        ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE),
        ButtonSlot(StartHighBeamStrobe(), RGB_WHITE),
    )
    definition = ButtonProfileDefinition(2, slots + (None,) * 9)
    assert (
        decode_button_profile(json.loads(canonical_button_profile_bytes(definition))) == definition
    )
    with pytest.raises(ValueError, match="must hold a ButtonSlot"):
        ButtonProfileDefinition(2, ("toggle_automatic_assistance",) + (None,) * 15)  # type: ignore[arg-type]
    raw = {
        "schema_version": 2,
        "slots": [_slot_json({"type": "toggle_button_pad_lamp_test"})] + [None] * 15,
    }
    with pytest.raises(ValueError, match="unsupported"):
        decode_button_profile(raw)
    with pytest.raises(ValueError, match="must be an integer"):
        ButtonProfileDefinition(True, (None,) * 16)


def _slot_json(command: dict[str, object], **overrides: object) -> dict[str, object]:
    return {
        "command": command,
        "colour": [0, 0, 255],
        "active_colour": None,
        "animation": None,
        **overrides,
    }


def test_stored_slot_shape_is_the_documented_json() -> None:
    definition = ButtonProfileDefinition(
        2,
        (ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), RGB_BLUE),) + (None,) * 15,
    )

    encoded = json.loads(canonical_button_profile_bytes(definition))

    assert encoded["schema_version"] == 2
    assert encoded["slots"][0] == {
        "command": {"type": "select_steering_mode", "mode": "auto"},
        "colour": [0, 0, 255],
        "active_colour": None,
        "animation": None,
    }
    assert encoded["slots"][1:] == [None] * 15


@pytest.mark.parametrize(
    "animation",
    [
        BreatheAnimation(2000, 8, 255),
        BlinkAnimation(400, 400),
    ],
)
def test_animation_round_trips_through_the_stored_shape(animation: object) -> None:
    definition = ButtonProfileDefinition(
        2,
        (ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE, animation=animation),)  # type: ignore[arg-type]
        + (None,) * 15,
    )

    assert (
        decode_button_profile(json.loads(canonical_button_profile_bytes(definition))) == definition
    )


def test_a_slot_rejects_values_the_pad_could_not_render() -> None:
    with pytest.raises(ValueError, match="three RGB bytes"):
        ButtonSlot(ToggleMaximumAssistance(), (0, 0, 256))
    with pytest.raises(ValueError, match="reserved"):
        ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE, active_colour=RGB_BLUE)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no active state"):
        ButtonSlot(StartHighBeamStrobe(), RGB_WHITE, animation=BlinkAnimation(400, 400))
    with pytest.raises(ValueError, match="no active state"):
        ButtonSlot(AdjustManualAssistance(1), RGB_WHITE, animation=BreatheAnimation(2000, 0, 255))
    with pytest.raises(ValueError, match="breathe period"):
        BreatheAnimation(249, 0, 255)
    with pytest.raises(ValueError, match="breathe period"):
        BreatheAnimation(10_001, 0, 255)
    with pytest.raises(ValueError, match="must not exceed its maximum"):
        BreatheAnimation(2000, 200, 199)
    with pytest.raises(ValueError, match="blink on duration"):
        BlinkAnimation(0, 400)
    with pytest.raises(ValueError, match="blink off duration"):
        BlinkAnimation(400, 10_001)


@pytest.mark.parametrize(
    "animation",
    [
        BreatheAnimation(250, 0, 0),
        BreatheAnimation(10_000, 255, 255),
        BreatheAnimation(2000, 200, 200),
        BlinkAnimation(1, 1),
        BlinkAnimation(10_000, 10_000),
    ],
)
def test_an_animation_exactly_on_its_bounds_is_accepted(animation: SlotAnimation) -> None:
    """The rejections above would also pass if the bounds were one step too tight."""

    assert ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE, animation=animation).animation is (
        animation
    )


@pytest.mark.parametrize("colour", [(0, 0, 0), (255, 255, 255)])
def test_a_colour_channel_at_either_extreme_is_accepted(colour: Rgb) -> None:
    assert ButtonSlot(ToggleMaximumAssistance(), colour).colour == colour


def _v1_definition() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "slots": [
            {"type": "select_steering_mode", "mode": "manual"},
            {"type": "toggle_automatic_assistance"},
            {"type": "adjust_manual_assistance", "delta": -1},
            {"type": "set_manual_assistance_level", "level": 3},
            {"type": "set_maximum_assistance", "enabled": True},
            {"type": "toggle_maximum_assistance"},
            {"type": "start_high_beam_strobe"},
        ]
        + [None] * 9,
    }


def _write_v1_row(
    path: Path,
    definition: dict[str, Any],
    *,
    schema_version: int = 1,
    fingerprint: str | None = None,
) -> None:
    """Write the row exactly as the build that only knew v1 would have written it."""

    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """UPDATE button_profiles
            SET schema_version=?, definition_json=?, definition_fingerprint=?
            WHERE profile_id=?""",
            (
                schema_version,
                canonical,
                fingerprint or sha256(canonical.encode()).hexdigest(),
                BUILT_IN_BUTTON_PROFILE_ID,
            ),
        )


def test_a_v1_row_is_migrated_on_read_and_rewritten_at_v2_on_save(tmp_path: Path) -> None:
    """A pre-existing database upgrades without operator action and keeps its bindings."""

    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    _write_v1_row(path, _v1_definition())

    migrated = repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)

    assert migrated is not None
    assert migrated.definition.schema_version == 2
    assert migrated.definition.slots[:7] == (
        ButtonSlot(SelectSteeringMode(SteeringMode.MANUAL), RGB_BLUE),
        ButtonSlot(ToggleAutomaticAssistance(), RGB_BLUE),
        ButtonSlot(AdjustManualAssistance(-1), RGB_WHITE),
        ButtonSlot(SetManualAssistanceLevel(3), RGB_WHITE),
        ButtonSlot(SetMaximumAssistance(True), RGB_WHITE),
        ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE),
        ButtonSlot(StartHighBeamStrobe(), RGB_WHITE),
    )
    assert migrated.definition.slots[7:] == (None,) * 9

    repo.update_profile(migrated.profile_id, migrated.revision, migrated.name, migrated.definition)

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT schema_version, definition_json FROM button_profiles WHERE profile_id=?",
            (BUILT_IN_BUTTON_PROFILE_ID,),
        ).fetchone()
    assert row[0] == 2
    assert json.loads(row[1])["slots"][0]["colour"] == [0, 0, 255]
    assert repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID) is not None


def test_a_schema_version_the_migration_does_not_recognise_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE button_profiles SET schema_version=99 WHERE profile_id=?",
            (BUILT_IN_BUTTON_PROFILE_ID,),
        )
    with pytest.raises(StoredProfileDataError, match="unsupported stored button profile"):
        repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)


@pytest.mark.parametrize(
    ("corrupt", "message"),
    [
        # A row whose column and payload disagree about which shape it is in.
        (
            lambda path: _write_v1_row(path, {**_v1_definition(), "schema_version": 2}),
            "schema_version column disagrees",
        ),
        # v1's own encoding, hand-edited: reformatted, and content changed under its hash.
        (
            lambda path: _write_v1_row(
                path, _v1_definition(), fingerprint=sha256(b"something else").hexdigest()
            ),
            "fingerprint mismatch",
        ),
    ],
)
def test_a_v1_row_is_verified_against_the_encoding_that_wrote_it(
    tmp_path: Path, corrupt: Callable[[Path], None], message: str
) -> None:
    """An old row fails as closed as a current one, checked by v1's encoding not this one."""

    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    corrupt(path)

    with pytest.raises(StoredProfileDataError, match=message):
        repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)


def test_a_noncanonical_v1_row_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite"
    repo = repository(path)
    repo.initialize()
    reformatted = json.dumps(_v1_definition(), indent=2)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """UPDATE button_profiles
            SET schema_version=1, definition_json=?, definition_fingerprint=?
            WHERE profile_id=?""",
            (
                reformatted,
                sha256(reformatted.encode()).hexdigest(),
                BUILT_IN_BUTTON_PROFILE_ID,
            ),
        )

    with pytest.raises(StoredProfileDataError, match="not canonical"):
        repo.get_profile(BUILT_IN_BUTTON_PROFILE_ID)


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
