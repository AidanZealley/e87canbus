import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from e87canbus.adapters.sqlite_profiles import (
    BUILT_IN_PROFILE_ID,
    BUILT_IN_PROFILE_NAME,
    CURRENT_MIGRATION_VERSION,
    SqliteSteeringProfileRepository,
    UnsupportedDatabaseVersionError,
)
from e87canbus.features.profile_repository import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRevisionConflictError,
    SteeringProfileStorageError,
    StoredProfileDataError,
)
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    canonical_steering_curve_bytes,
)

NOW = datetime(2026, 7, 14, 12, 30, tzinfo=UTC)
PROFILE_ID = UUID("12345678-1234-4678-9234-567812345678")


def _repository(path: Path) -> SqliteSteeringProfileRepository:
    return SqliteSteeringProfileRepository(
        path,
        clock=lambda: NOW,
        identifier_factory=lambda: PROFILE_ID,
    )


def _changed_definition() -> SteeringCurveDefinition:
    points = list(BUILT_IN_STEERING_CURVE.points)
    points[1] = SteeringCurvePoint(speed_deci_kph=100, assistance_per_mille=800)
    return replace(BUILT_IN_STEERING_CURVE, points=tuple(points))


def _raw_update(path: Path, sql: str, parameters: tuple[object, ...]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(sql, parameters)


def test_fresh_migration_and_repeat_initialization(tmp_path: Path) -> None:
    path = tmp_path / "profiles.sqlite3"
    repository = _repository(path)

    repository.initialize()
    repository.initialize()

    with sqlite3.connect(path) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert versions == [(CURRENT_MIGRATION_VERSION,)]
    assert journal_mode == "wal"
    assert repository.list_profiles() == (repository.get_profile(BUILT_IN_PROFILE_ID),)


def test_builtin_seed_is_stable_and_not_replaced_on_repeat_startup(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    seed = repository.get_profile(BUILT_IN_PROFILE_ID)
    assert seed is not None
    assert seed.name == BUILT_IN_PROFILE_NAME

    renamed = repository.update_profile(
        seed.profile_id, seed.revision, "My edited default", _changed_definition()
    )
    repository.initialize()

    assert repository.get_profile(BUILT_IN_PROFILE_ID) == renamed


def test_nonempty_catalog_is_not_reseeded_after_seed_deletion(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)
    repository.delete_profile(BUILT_IN_PROFILE_ID, 1)

    repository.initialize()

    assert repository.list_profiles() == (created,)


def test_create_get_and_case_insensitive_list_order(tmp_path: Path) -> None:
    path = tmp_path / "profiles.sqlite3"
    identifiers = iter(
        (
            UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        )
    )
    repository = SqliteSteeringProfileRepository(
        path, clock=lambda: NOW, identifier_factory=lambda: next(identifiers)
    )
    repository.initialize()

    wet = repository.create_profile("wet", _changed_definition())
    dry = repository.create_profile("Dry", BUILT_IN_STEERING_CURVE)

    assert repository.get_profile(wet.profile_id) == wet
    assert repository.get_profile("00000000-0000-4000-8000-ffffffffffff") is None
    assert tuple(profile.name for profile in repository.list_profiles()) == (
        BUILT_IN_PROFILE_NAME,
        "Dry",
        "wet",
    )
    assert dry.revision == 1


def test_create_rejects_case_insensitive_name_conflict(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()

    with pytest.raises(ProfileNameConflictError) as caught:
        repository.create_profile(BUILT_IN_PROFILE_NAME.upper(), BUILT_IN_STEERING_CURVE)

    assert caught.value.name == BUILT_IN_PROFILE_NAME.upper()


def test_update_rejects_case_insensitive_name_conflict(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)

    with pytest.raises(ProfileNameConflictError):
        repository.update_profile(
            created.profile_id,
            created.revision,
            BUILT_IN_PROFILE_NAME.upper(),
            created.definition,
        )

    assert repository.get_profile(created.profile_id) == created


def test_write_runs_domain_validation_before_opening_database(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "missing-parent" / "profiles.sqlite3")

    with pytest.raises(ValueError, match="trimmed"):
        repository.create_profile(" Track ", BUILT_IN_STEERING_CURVE)


def test_update_round_trips_integer_definition_and_increments_once(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)

    updated = repository.update_profile(
        created.profile_id, created.revision, "Wet", _changed_definition()
    )

    assert updated.revision == created.revision + 1
    assert updated.created_at == created.created_at
    assert updated.definition == _changed_definition()
    assert tuple(
        (point.speed_deci_kph, point.assistance_per_mille)
        for point in updated.definition.points
    ) == (
        (0, 1000),
        (100, 800),
        (200, 778),
        (300, 667),
        (600, 381),
        (1000, 0),
        (1600, 0),
        (2500, 0),
    )
    assert repository.get_profile(created.profile_id) == updated


def test_update_rejects_stale_revision_and_preserves_newer_value(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)
    updated = repository.update_profile(
        created.profile_id, created.revision, "Wet", _changed_definition()
    )

    with pytest.raises(ProfileRevisionConflictError) as caught:
        repository.update_profile(
            created.profile_id, created.revision, "Stale", BUILT_IN_STEERING_CURVE
        )

    assert caught.value.actual_revision == updated.revision
    assert repository.get_profile(created.profile_id) == updated


def test_stale_delete_conflicts_and_missing_delete_is_not_found(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)
    updated = repository.update_profile(
        created.profile_id, created.revision, created.name, created.definition
    )

    with pytest.raises(ProfileRevisionConflictError):
        repository.delete_profile(created.profile_id, created.revision)
    with pytest.raises(ProfileNotFoundError):
        repository.delete_profile("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", 1)

    assert repository.get_profile(created.profile_id) == updated


def test_delete_removes_matching_revision(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "profiles.sqlite3")
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)

    repository.delete_profile(created.profile_id, created.revision)

    assert repository.get_profile(created.profile_id) is None


@pytest.mark.parametrize(
    ("sql", "value", "message"),
    [
        (
            "UPDATE steering_profiles SET definition_json = ? WHERE profile_id = ?",
            "{not-json",
            "invalid stored steering profile",
        ),
        (
            "UPDATE steering_profiles SET definition_fingerprint = ? WHERE profile_id = ?",
            "0" * 64,
            "fingerprint mismatch",
        ),
        (
            "UPDATE steering_profiles SET schema_version = ? WHERE profile_id = ?",
            2,
            "schema_version column disagrees",
        ),
        (
            "UPDATE steering_profiles SET interpolation = ? WHERE profile_id = ?",
            "monotone-cubic-v1",
            "interpolation column disagrees",
        ),
    ],
)
def test_corrupt_columns_and_malformed_json_fail_closed(
    tmp_path: Path, sql: str, value: object, message: str
) -> None:
    path = tmp_path / "profiles.sqlite3"
    repository = _repository(path)
    repository.initialize()
    _raw_update(path, sql, (value, BUILT_IN_PROFILE_ID))

    with pytest.raises(StoredProfileDataError, match=message):
        repository.get_profile(BUILT_IN_PROFILE_ID)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "unsupported steering curve schema_version"),
        ("interpolation", "future-v2", "not a valid CurveInterpolation"),
    ],
)
def test_unsupported_future_definition_fails_closed(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    path = tmp_path / "profiles.sqlite3"
    repository = _repository(path)
    repository.initialize()
    raw_definition = json.loads(canonical_steering_curve_bytes(BUILT_IN_STEERING_CURVE))
    raw_definition[field] = value
    definition_json = json.dumps(
        raw_definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    _raw_update(
        path,
        f"UPDATE steering_profiles SET {field} = ?, definition_json = ? WHERE profile_id = ?",
        (value, definition_json, BUILT_IN_PROFILE_ID),
    )

    with pytest.raises(StoredProfileDataError, match=message):
        repository.get_profile(BUILT_IN_PROFILE_ID)


def test_failed_update_rolls_back_the_transaction(tmp_path: Path) -> None:
    path = tmp_path / "profiles.sqlite3"
    repository = _repository(path)
    repository.initialize()
    created = repository.create_profile("Track", BUILT_IN_STEERING_CURVE)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_profile_update
            BEFORE UPDATE ON steering_profiles
            BEGIN
                SELECT RAISE(ABORT, 'injected failure');
            END
            """
        )

    with pytest.raises(SteeringProfileStorageError):
        repository.update_profile(
            created.profile_id, created.revision, created.name, _changed_definition()
        )

    assert repository.get_profile(created.profile_id) == created


def test_newer_migration_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "profiles.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at_utc TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (?, ?)",
            (CURRENT_MIGRATION_VERSION + 1, "2026-07-14T12:30:00.000000Z"),
        )

    with pytest.raises(UnsupportedDatabaseVersionError) as caught:
        _repository(path).initialize()

    assert caught.value.found_version == CURRENT_MIGRATION_VERSION + 1


def test_reopening_repository_retains_profiles(tmp_path: Path) -> None:
    path = tmp_path / "profiles.sqlite3"
    first_repository = _repository(path)
    first_repository.initialize()
    created = first_repository.create_profile("Track", _changed_definition())

    reopened_repository = _repository(path)

    assert reopened_repository.get_profile(created.profile_id) == created


def test_sqlite_exceptions_are_wrapped_at_adapter_boundary(tmp_path: Path) -> None:
    repository = _repository(tmp_path / "missing-parent" / "profiles.sqlite3")

    with pytest.raises(SteeringProfileStorageError) as caught:
        repository.initialize()

    assert not isinstance(caught.value, sqlite3.Error)
