"""Shared SQLite connection policy and application schema migrations."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from e87canbus.domain.application_settings import DEFAULT_APPLICATION_SETTINGS
from e87canbus.domain.steering import (
    BUILT_IN_STEERING_CURVE,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    canonical_steering_curve_bytes,
    steering_curve_fingerprint,
)
from e87canbus.domain.timestamps import canonical_utc_timestamp

CURRENT_MIGRATION_VERSION = 4
BUILT_IN_PROFILE_ID = "00000000-0000-4000-8000-000000000001"
BUILT_IN_PROFILE_NAME = "Built-in default"


class ApplicationDatabaseError(Exception):
    """The shared application database could not be opened or migrated safely."""


class UnsupportedDatabaseVersionError(ApplicationDatabaseError):
    def __init__(self, found_version: int, supported_version: int) -> None:
        self.found_version = found_version
        self.supported_version = supported_version
        super().__init__(
            f"application database version {found_version} is newer than supported "
            f"version {supported_version}"
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqliteApplicationDatabase:
    """Own connection durability policy and ordered migrations for one SQLite file."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.database_path = str(database_path)
        self.clock = clock

    def connect(self) -> sqlite3.Connection:
        try:
            connection = sqlite3.connect(self.database_path, timeout=5.0)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except sqlite3.Error as error:
            raise ApplicationDatabaseError("could not open the application database") from error

    def initialize(self) -> None:
        """Apply every missing migration and seed without rewriting existing rows."""

        connection = self.connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at_utc TEXT NOT NULL
                )
                """
            )
            versions = tuple(
                row["version"]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall()
            )
            self._validate_migration_versions(versions)
            next_version = 1 if not versions else versions[-1] + 1
            for version in range(next_version, CURRENT_MIGRATION_VERSION + 1):
                if version == 1:
                    self._apply_migration_1(connection)
                elif version == 2:
                    self._apply_migration_2(connection)
                elif version == 3:
                    self._apply_migration_3(connection)
                elif version == 4:
                    self._apply_migration_4(connection)
            # Migration 1 historically restored the built-in only when the whole
            # catalog was empty. Preserve that startup behavior for upgraded files.
            self._seed_profiles_if_empty(connection)
            connection.commit()
        except ApplicationDatabaseError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise ApplicationDatabaseError(
                "could not initialize the application database"
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _validate_migration_versions(versions: tuple[Any, ...]) -> None:
        if any(type(version) is not int or version < 1 for version in versions):
            raise ApplicationDatabaseError("invalid application database migration history")
        if versions and versions[-1] > CURRENT_MIGRATION_VERSION:
            raise UnsupportedDatabaseVersionError(versions[-1], CURRENT_MIGRATION_VERSION)
        expected = tuple(range(1, len(versions) + 1))
        if versions != expected:
            raise ApplicationDatabaseError("incomplete application database migration history")

    def _record_migration(self, connection: sqlite3.Connection, version: int) -> None:
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at_utc) VALUES (?, ?)",
            (version, canonical_utc_timestamp(self.clock())),
        )

    def _apply_migration_1(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
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
            )
            """
        )
        self._record_migration(connection, 1)

    def _apply_migration_2(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE application_settings (
                singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
                revision INTEGER NOT NULL CHECK (revision > 0),
                speed_unit TEXT NOT NULL,
                temperature_unit TEXT NOT NULL,
                oil_warning_c REAL NOT NULL,
                oil_critical_c REAL NOT NULL,
                coolant_warning_c REAL NOT NULL,
                coolant_critical_c REAL NOT NULL,
                shift_stage_1_rpm INTEGER NOT NULL,
                shift_stage_2_rpm INTEGER NOT NULL,
                redline_rpm INTEGER NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )
        settings = DEFAULT_APPLICATION_SETTINGS
        connection.execute(
            """
            INSERT INTO application_settings (
                singleton_id, revision, speed_unit, temperature_unit,
                oil_warning_c, oil_critical_c, coolant_warning_c, coolant_critical_c,
                shift_stage_1_rpm, shift_stage_2_rpm, redline_rpm, updated_at_utc
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                settings.revision,
                settings.speed_unit.value,
                settings.temperature_unit.value,
                settings.oil_warning_c,
                settings.oil_critical_c,
                settings.coolant_warning_c,
                settings.coolant_critical_c,
                settings.shift_stage_1_rpm,
                settings.shift_stage_2_rpm,
                settings.redline_rpm,
                settings.updated_at,
            ),
        )
        self._record_migration(connection, 2)

    def _apply_migration_3(self, connection: sqlite3.Connection) -> None:
        self._record_migration(connection, 3)

    def _apply_migration_4(self, connection: sqlite3.Connection) -> None:
        """Replace algorithm-tagged profiles with points-only smooth definitions."""

        rows = connection.execute(
            "SELECT profile_id, revision, definition_json FROM steering_profiles"
        ).fetchall()
        timestamp = canonical_utc_timestamp(self.clock())
        for row in rows:
            raw_definition = json.loads(row["definition_json"])
            had_interpolation = raw_definition.pop("interpolation", None) is not None
            definition = SteeringCurveDefinition(
                schema_version=raw_definition["schema_version"],
                points=tuple(
                    SteeringCurvePoint(
                        speed_deci_kph=point["speed_deci_kph"],
                        assistance_per_mille=point["assistance_per_mille"],
                    )
                    for point in raw_definition["points"]
                ),
            )
            definition_json = canonical_steering_curve_bytes(definition).decode("utf-8")
            connection.execute(
                """
                UPDATE steering_profiles
                SET revision = ?, definition_json = ?,
                    definition_fingerprint = ?, updated_at_utc = ?
                WHERE profile_id = ?
                """,
                (
                    row["revision"] + (1 if had_interpolation else 0),
                    definition_json,
                    steering_curve_fingerprint(definition),
                    timestamp,
                    row["profile_id"],
                ),
            )
        connection.execute("ALTER TABLE steering_profiles RENAME TO steering_profiles_legacy")
        connection.execute(
            """
            CREATE TABLE steering_profiles (
                profile_id TEXT PRIMARY KEY,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                revision INTEGER NOT NULL CHECK (revision > 0),
                schema_version INTEGER NOT NULL,
                definition_json TEXT NOT NULL,
                definition_fingerprint TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO steering_profiles
            SELECT profile_id, name, revision, schema_version, definition_json,
                   definition_fingerprint, created_at_utc, updated_at_utc
            FROM steering_profiles_legacy
            """
        )
        connection.execute("DROP TABLE steering_profiles_legacy")
        self._record_migration(connection, 4)

    def _seed_profiles_if_empty(self, connection: sqlite3.Connection) -> None:
        count = connection.execute("SELECT COUNT(*) FROM steering_profiles").fetchone()[0]
        if count:
            return
        timestamp = canonical_utc_timestamp(self.clock())
        definition_json = canonical_steering_curve_bytes(BUILT_IN_STEERING_CURVE).decode("utf-8")
        connection.execute(
            """
            INSERT INTO steering_profiles (
                profile_id, name, revision, schema_version,
                definition_json, definition_fingerprint, created_at_utc, updated_at_utc
            ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                BUILT_IN_PROFILE_ID,
                BUILT_IN_PROFILE_NAME,
                BUILT_IN_STEERING_CURVE.schema_version,
                definition_json,
                steering_curve_fingerprint(BUILT_IN_STEERING_CURVE),
                timestamp,
                timestamp,
            ),
        )
