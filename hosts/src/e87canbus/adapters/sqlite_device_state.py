"""Durable desired configuration and last-reported button-pad status."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from e87canbus.adapters.sqlite_database import ApplicationDatabaseError, SqliteApplicationDatabase
from e87canbus.api.auth import DeviceRole
from e87canbus.api.models.button_pad import ButtonPadScene, ButtonPadStatus
from e87canbus.domain.timestamps import canonical_utc_timestamp, validate_canonical_utc_timestamp


class DeviceStateStorageError(Exception):
    """Device state could not be read or committed safely."""


class DeviceRoleMismatchError(DeviceStateStorageError):
    """A stored device ID belongs to a different role."""


@dataclass(frozen=True, slots=True)
class StoredButtonPadConfiguration:
    device_id: str
    role: DeviceRole
    generation: int
    configuration: ButtonPadScene


@dataclass(frozen=True, slots=True)
class StoredButtonPadStatus:
    device_id: str
    role: DeviceRole
    status: ButtonPadStatus
    received_at_utc: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqliteDeviceStateRepository:
    """One complete scene and one last status per authenticated device ID."""

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

    def get_or_create_configuration(
        self, device_id: str, role: DeviceRole, default: ButtonPadScene
    ) -> StoredButtonPadConfiguration:
        self._validate_identity(device_id, role)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._check_role(connection, device_id, role)
            row = connection.execute(
                "SELECT * FROM device_configurations WHERE device_id = ?", (device_id,)
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO device_configurations VALUES (?, ?, 0, ?)",
                    (device_id, role.value, default.model_dump_json()),
                )
                result = StoredButtonPadConfiguration(device_id, role, 0, default)
            else:
                result = self._configuration_from_row(row, role)
            connection.commit()
            return result
        except (DeviceStateStorageError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, DeviceStateStorageError):
                raise
            raise DeviceStateStorageError("could not read device configuration") from error
        finally:
            connection.close()

    def replace_configuration_if_changed(
        self, device_id: str, role: DeviceRole, configuration: ButtonPadScene
    ) -> StoredButtonPadConfiguration:
        self._validate_identity(device_id, role)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._check_role(connection, device_id, role)
            row = connection.execute(
                "SELECT * FROM device_configurations WHERE device_id = ?", (device_id,)
            ).fetchone()
            if row is None:
                raise DeviceStateStorageError("device configuration has not been initialized")
            current = self._configuration_from_row(row, role)
            if current.configuration == configuration:
                connection.commit()
                return current
            generation = current.generation + 1
            connection.execute(
                "UPDATE device_configurations SET generation = ?, configuration_json = ? "
                "WHERE device_id = ?",
                (generation, configuration.model_dump_json(), device_id),
            )
            connection.commit()
            return StoredButtonPadConfiguration(device_id, role, generation, configuration)
        except (DeviceStateStorageError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, DeviceStateStorageError):
                raise
            raise DeviceStateStorageError("could not replace device configuration") from error
        finally:
            connection.close()

    def get_configuration(
        self, device_id: str, role: DeviceRole
    ) -> StoredButtonPadConfiguration | None:
        self._validate_identity(device_id, role)
        connection = self._connect()
        try:
            self._check_role(connection, device_id, role)
            row = connection.execute(
                "SELECT * FROM device_configurations WHERE device_id = ?", (device_id,)
            ).fetchone()
            return None if row is None else self._configuration_from_row(row, role)
        except sqlite3.Error as error:
            raise DeviceStateStorageError("could not read device configuration") from error
        finally:
            connection.close()

    def list_button_pad_configurations(self) -> tuple[StoredButtonPadConfiguration, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM device_configurations WHERE role = ? ORDER BY device_id",
                (DeviceRole.BUTTON_PAD.value,),
            ).fetchall()
            return tuple(self._configuration_from_row(row, DeviceRole.BUTTON_PAD) for row in rows)
        except sqlite3.Error as error:
            raise DeviceStateStorageError("could not list device configurations") from error
        finally:
            connection.close()

    def upsert_status(
        self, device_id: str, role: DeviceRole, status: ButtonPadStatus
    ) -> StoredButtonPadStatus:
        self._validate_identity(device_id, role)
        received_at = canonical_utc_timestamp(self._clock())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._check_role(connection, device_id, role)
            connection.execute(
                """INSERT INTO device_statuses (
                    device_id, role, status_version, applied_configuration_generation,
                    configuration_error, device_json, received_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    status_version=excluded.status_version,
                    applied_configuration_generation=excluded.applied_configuration_generation,
                    configuration_error=excluded.configuration_error,
                    device_json=excluded.device_json,
                    received_at_utc=excluded.received_at_utc""",
                (
                    device_id,
                    role.value,
                    status.status_version,
                    status.applied_configuration_generation,
                    status.configuration_error,
                    status.device.model_dump_json(),
                    received_at,
                ),
            )
            connection.commit()
            return StoredButtonPadStatus(device_id, role, status, received_at)
        except (DeviceStateStorageError, sqlite3.Error) as error:
            connection.rollback()
            if isinstance(error, DeviceStateStorageError):
                raise
            raise DeviceStateStorageError("could not store device status") from error
        finally:
            connection.close()

    def get_status(self, device_id: str, role: DeviceRole) -> StoredButtonPadStatus | None:
        self._validate_identity(device_id, role)
        connection = self._connect()
        try:
            self._check_role(connection, device_id, role)
            row = connection.execute(
                "SELECT * FROM device_statuses WHERE device_id = ?", (device_id,)
            ).fetchone()
            return None if row is None else self._status_from_row(row, role)
        except sqlite3.Error as error:
            raise DeviceStateStorageError("could not read device status") from error
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._database.connect()
        except ApplicationDatabaseError as error:
            raise DeviceStateStorageError("could not open the application database") from error

    @staticmethod
    def _validate_identity(device_id: str, role: DeviceRole) -> None:
        try:
            if str(UUID(device_id)) != device_id:
                raise ValueError("device ID must be canonical")
        except (ValueError, TypeError) as error:
            raise ValueError("device ID must be a canonical UUID") from error
        if role is not DeviceRole.BUTTON_PAD:
            raise ValueError("button-pad state requires the button-pad role")

    @staticmethod
    def _assert_role(stored: str, role: DeviceRole) -> None:
        if stored != role.value:
            raise DeviceRoleMismatchError("stored device role does not match authenticated role")

    def _check_role(self, connection: sqlite3.Connection, device_id: str, role: DeviceRole) -> None:
        for table in ("device_configurations", "device_statuses"):
            row = connection.execute(
                f"SELECT role FROM {table} WHERE device_id = ?", (device_id,)
            ).fetchone()
            if row is not None:
                self._assert_role(row["role"], role)

    def _configuration_from_row(
        self, row: sqlite3.Row, role: DeviceRole
    ) -> StoredButtonPadConfiguration:
        self._assert_role(row["role"], role)
        try:
            generation = row["generation"]
            if type(generation) is not int or generation < 0:
                raise ValueError("invalid generation")
            configuration = ButtonPadScene.model_validate_json(row["configuration_json"])
            return StoredButtonPadConfiguration(row["device_id"], role, generation, configuration)
        except (ValidationError, ValueError, TypeError) as error:
            raise DeviceStateStorageError("invalid stored device configuration") from error

    def _status_from_row(self, row: sqlite3.Row, role: DeviceRole) -> StoredButtonPadStatus:
        self._assert_role(row["role"], role)
        try:
            received_at = row["received_at_utc"]
            validate_canonical_utc_timestamp(received_at, "received_at_utc")
            status = ButtonPadStatus.model_validate(
                {
                    "status_version": row["status_version"],
                    "applied_configuration_generation": row["applied_configuration_generation"],
                    "configuration_error": row["configuration_error"],
                    "device": json.loads(row["device_json"]),
                }
            )
            return StoredButtonPadStatus(row["device_id"], role, status, received_at)
        except (ValidationError, ValueError, TypeError) as error:
            raise DeviceStateStorageError("invalid stored device status") from error
