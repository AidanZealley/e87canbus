import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from e87canbus.adapters.sqlite_database import (
    BUILT_IN_PROFILE_ID,
    CURRENT_MIGRATION_VERSION,
    SqliteApplicationDatabase,
)
from e87canbus.adapters.sqlite_profiles import SqliteSteeringProfileRepository
from e87canbus.adapters.sqlite_settings import SqliteApplicationSettingsRepository
from e87canbus.features.application_settings import (
    DEFAULT_APPLICATION_SETTINGS,
    SpeedUnit,
)
from e87canbus.features.settings_repository import (
    SettingsRevisionConflictError,
    SettingsStorageError,
    StoredSettingsDataError,
)
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    canonical_steering_curve_bytes,
)

NOW = datetime(2026, 7, 14, 12, 30, tzinfo=UTC)


def repositories(path: Path):
    database = SqliteApplicationDatabase(path, clock=lambda: NOW)
    return (
        database,
        SqliteSteeringProfileRepository(database, clock=lambda: NOW),
        SqliteApplicationSettingsRepository(database, clock=lambda: NOW),
    )


def create_version_1_database(path: Path) -> None:
    raw_definition = json.loads(canonical_steering_curve_bytes(BUILT_IN_STEERING_CURVE))
    raw_definition["interpolation"] = "linear-v1"
    definition_json = json.dumps(raw_definition, sort_keys=True, separators=(",", ":"))
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at_utc TEXT NOT NULL
            );
            CREATE TABLE steering_profiles (
                profile_id TEXT PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                revision INTEGER NOT NULL CHECK (revision > 0),
                schema_version INTEGER NOT NULL,
                interpolation TEXT NOT NULL,
                definition_json TEXT NOT NULL,
                definition_fingerprint TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO schema_migrations VALUES (1, ?)",
            ("2026-07-14T10:00:00.000000Z",),
        )
        connection.execute(
            """
            INSERT INTO steering_profiles VALUES (?, ?, 4, 1, ?, ?, ?, ?, ?)
            """,
            (
                BUILT_IN_PROFILE_ID,
                "Preserved profile",
                "linear-v1",
                definition_json,
                "legacy-fingerprint",
                "2026-07-14T10:00:00.000000Z",
                "2026-07-14T11:00:00.000000Z",
            ),
        )


def test_fresh_database_applies_all_migrations_and_seeds(tmp_path: Path) -> None:
    path = tmp_path / "application.sqlite3"
    database, profiles, settings = repositories(path)

    database.initialize()

    with sqlite3.connect(path) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert versions == [(1,), (2,), (3,), (4,)]
    assert journal_mode == "wal"
    assert profiles.get_profile(BUILT_IN_PROFILE_ID) is not None
    assert settings.get_settings() == DEFAULT_APPLICATION_SETTINGS


def test_version_1_upgrade_converts_legacy_profile_to_smooth(tmp_path: Path) -> None:
    path = tmp_path / "application.sqlite3"
    create_version_1_database(path)
    database, profiles, settings = repositories(path)
    database.initialize()

    after = profiles.get_profile(BUILT_IN_PROFILE_ID)
    assert after is not None
    assert after.revision == 5
    assert settings.get_settings() == DEFAULT_APPLICATION_SETTINGS
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall() == [(1,), (2,), (3,), (CURRENT_MIGRATION_VERSION,)]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(steering_profiles)")
        }
        stored_json = connection.execute(
            "SELECT definition_json FROM steering_profiles WHERE profile_id = ?",
            (BUILT_IN_PROFILE_ID,),
        ).fetchone()[0]
    assert "interpolation" not in columns
    assert "interpolation" not in json.loads(stored_json)


def test_repeat_initialization_preserves_edited_settings(tmp_path: Path) -> None:
    database, _, settings = repositories(tmp_path / "application.sqlite3")
    database.initialize()
    edited = settings.update_settings(
        1,
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), speed_unit=SpeedUnit.KMH),
    )

    database.initialize()

    assert settings.get_settings() == edited


def test_round_trip_increments_once_and_uses_one_new_timestamp(tmp_path: Path) -> None:
    path = tmp_path / "application.sqlite3"
    database = SqliteApplicationDatabase(path, clock=lambda: NOW)
    database.initialize()
    settings = SqliteApplicationSettingsRepository(database, clock=lambda: NOW)
    candidate = replace(
        DEFAULT_APPLICATION_SETTINGS.editable_values(),
        speed_unit=SpeedUnit.KMH,
        oil_warning_c=124.5,
    )

    updated = settings.update_settings(1, candidate)

    assert updated.revision == 2
    assert updated.editable_values() == candidate
    assert updated.updated_at == "2026-07-14T12:30:00.000000Z"
    assert settings.get_settings() == updated


def test_stale_writer_loses_and_newer_data_remains(tmp_path: Path) -> None:
    database, _, settings = repositories(tmp_path / "application.sqlite3")
    database.initialize()
    winner = settings.update_settings(
        1,
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), speed_unit=SpeedUnit.KMH),
    )

    with pytest.raises(SettingsRevisionConflictError) as caught:
        settings.update_settings(1, DEFAULT_APPLICATION_SETTINGS.editable_values())

    assert caught.value.current_revision == 2
    assert settings.get_settings() == winner


def test_concurrent_same_revision_writers_allow_one_success(tmp_path: Path) -> None:
    database, _, settings = repositories(tmp_path / "application.sqlite3")
    database.initialize()
    candidates = (
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), oil_warning_c=124.0),
        replace(DEFAULT_APPLICATION_SETTINGS.editable_values(), oil_warning_c=123.0),
    )

    def write(candidate):
        try:
            return settings.update_settings(1, candidate)
        except SettingsRevisionConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(write, candidates))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, SettingsRevisionConflictError) for result in results) == 1
    assert settings.get_settings().revision == 2


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("speed_unit", "knots"),
        ("revision", "invalid"),
        ("oil_warning_c", 140.0),
        ("shift_stage_1_rpm", 6800.5),
        ("updated_at_utc", "not-a-timestamp"),
    ],
)
def test_corrupt_settings_row_fails_closed(
    tmp_path: Path, column: str, value: object
) -> None:
    path = tmp_path / "application.sqlite3"
    database, _, settings = repositories(path)
    database.initialize()
    with sqlite3.connect(path) as connection:
        connection.execute(f"UPDATE application_settings SET {column} = ?", (value,))

    with pytest.raises(StoredSettingsDataError):
        settings.get_settings()


def test_missing_database_is_wrapped_at_settings_boundary(tmp_path: Path) -> None:
    settings = SqliteApplicationSettingsRepository(
        tmp_path / "missing-parent" / "application.sqlite3"
    )

    with pytest.raises(SettingsStorageError) as caught:
        settings.get_settings()

    assert not isinstance(caught.value, sqlite3.Error)
