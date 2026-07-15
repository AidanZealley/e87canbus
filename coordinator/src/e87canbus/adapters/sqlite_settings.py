"""SQLite repository for the singleton revisioned application settings."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from e87canbus.adapters.sqlite_database import (
    ApplicationDatabaseError,
    SqliteApplicationDatabase,
)
from e87canbus.features.application_settings import (
    ApplicationSettings,
    ApplicationSettingsUpdate,
    SpeedUnit,
    TemperatureUnit,
    validate_application_settings_update,
    validate_expected_revision,
)
from e87canbus.features.settings_repository import (
    ApplicationSettingsRepositoryError,
    SettingsRevisionConflictError,
    SettingsStorageError,
    StoredSettingsDataError,
)
from e87canbus.features.timestamps import canonical_utc_timestamp


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqliteApplicationSettingsRepository:
    """Read and atomically replace the one authoritative settings document."""

    def __init__(
        self,
        database: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._database = (
            database
            if isinstance(database, SqliteApplicationDatabase)
            else SqliteApplicationDatabase(database, clock=clock)
        )
        self._clock = clock

    def get_settings(self) -> ApplicationSettings:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM application_settings WHERE singleton_id = 1"
            ).fetchone()
            if row is None:
                raise StoredSettingsDataError("singleton row is missing")
            return self._settings_from_row(row)
        except ApplicationSettingsRepositoryError:
            raise
        except sqlite3.Error as error:
            raise SettingsStorageError("could not read application settings") from error
        finally:
            connection.close()

    def update_settings(
        self,
        expected_revision: int,
        candidate: ApplicationSettingsUpdate,
    ) -> ApplicationSettings:
        validate_expected_revision(expected_revision)
        validate_application_settings_update(candidate)
        timestamp = canonical_utc_timestamp(self._clock())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE application_settings
                SET revision = revision + 1,
                    speed_unit = ?, temperature_unit = ?,
                    oil_warning_c = ?, oil_critical_c = ?,
                    coolant_warning_c = ?, coolant_critical_c = ?,
                    shift_stage_1_rpm = ?, shift_stage_2_rpm = ?, redline_rpm = ?,
                    updated_at_utc = ?
                WHERE singleton_id = 1 AND revision = ?
                """,
                (
                    candidate.speed_unit.value,
                    candidate.temperature_unit.value,
                    candidate.oil_warning_c,
                    candidate.oil_critical_c,
                    candidate.coolant_warning_c,
                    candidate.coolant_critical_c,
                    candidate.shift_stage_1_rpm,
                    candidate.shift_stage_2_rpm,
                    candidate.redline_rpm,
                    timestamp,
                    expected_revision,
                ),
            )
            if cursor.rowcount == 0:
                current_revision = self._current_revision(connection)
                connection.rollback()
                raise SettingsRevisionConflictError(expected_revision, current_revision)
            row = connection.execute(
                "SELECT * FROM application_settings WHERE singleton_id = 1"
            ).fetchone()
            if row is None:
                raise SettingsStorageError("committed application settings row disappeared")
            stored = self._settings_from_row(row)
            connection.commit()
            return stored
        except ApplicationSettingsRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise SettingsStorageError("could not update application settings") from error
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._database.connect()
        except ApplicationDatabaseError as error:
            raise SettingsStorageError("could not open the application database") from error

    @staticmethod
    def _settings_from_row(row: sqlite3.Row) -> ApplicationSettings:
        try:
            if row["singleton_id"] != 1:
                raise ValueError("singleton_id must be 1")
            return ApplicationSettings(
                revision=row["revision"],
                speed_unit=SpeedUnit(row["speed_unit"]),
                temperature_unit=TemperatureUnit(row["temperature_unit"]),
                oil_warning_c=row["oil_warning_c"],
                oil_critical_c=row["oil_critical_c"],
                coolant_warning_c=row["coolant_warning_c"],
                coolant_critical_c=row["coolant_critical_c"],
                shift_stage_1_rpm=row["shift_stage_1_rpm"],
                shift_stage_2_rpm=row["shift_stage_2_rpm"],
                redline_rpm=row["redline_rpm"],
                updated_at=row["updated_at_utc"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StoredSettingsDataError(str(error)) from error

    @staticmethod
    def _current_revision(connection: sqlite3.Connection) -> int:
        row = connection.execute(
            "SELECT revision FROM application_settings WHERE singleton_id = 1"
        ).fetchone()
        if row is None:
            raise StoredSettingsDataError("singleton row is missing")
        revision = row["revision"]
        if type(revision) is not int or revision < 1:
            raise StoredSettingsDataError("revision must be a positive integer")
        return revision
