"""SQLite persistence for button-pad profiles."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    BUILT_IN_BUTTON_PROFILE_ID,
    ApplicationDatabaseError,
    SqliteApplicationDatabase,
)
from e87canbus.domain.button_profile_repository import (
    ButtonProfileNameConflictError,
    ButtonProfileNotFoundError,
    ButtonProfileProtectedError,
    ButtonProfileRepositoryError,
    ButtonProfileRevisionConflictError,
    ButtonProfileStorageError,
    StoredButtonProfileDataError,
)
from e87canbus.domain.button_profiles import (
    ButtonProfileDefinition,
    StoredButtonProfile,
    button_profile_fingerprint,
    canonical_button_profile_bytes,
    decode_button_profile,
    empty_button_profile_definition,
    validate_button_profile_name,
)
from e87canbus.domain.timestamps import canonical_utc_timestamp


def _now() -> datetime:
    return datetime.now(UTC)


class SqliteButtonProfileRepository:
    def __init__(
        self,
        database_path: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = _now,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._database = (
            database_path
            if isinstance(database_path, SqliteApplicationDatabase)
            else SqliteApplicationDatabase(database_path, clock=clock)
        )
        self._clock, self._identifier_factory = clock, identifier_factory

    def initialize(self) -> None:
        try:
            self._database.initialize()
        except ApplicationDatabaseError as error:
            raise ButtonProfileStorageError("could not initialize application database") from error

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._database.connect()
        except ApplicationDatabaseError as error:
            raise ButtonProfileStorageError("could not open button profile database") from error

    def list_profiles(self) -> tuple[StoredButtonProfile, ...]:
        with self._connect() as connection:
            try:
                return tuple(
                    self._from_row(r)
                    for r in connection.execute(
                        "SELECT * FROM button_profiles ORDER BY name COLLATE NOCASE, profile_id"
                    )
                )
            except sqlite3.Error as error:
                raise ButtonProfileStorageError("could not list button profiles") from error

    def get_profile(self, profile_id: str) -> StoredButtonProfile | None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT * FROM button_profiles WHERE profile_id=?", (profile_id,)
                ).fetchone()
                return None if row is None else self._from_row(row)
            except ButtonProfileRepositoryError:
                raise
            except sqlite3.Error as error:
                raise ButtonProfileStorageError(
                    f"could not read button profile {profile_id}"
                ) from error

    def get_selected_profile(self) -> StoredButtonProfile:
        """Return the selected row, repairing a missing singleton deterministically."""

        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """SELECT p.* FROM selected_button_profile s
                    JOIN button_profiles p ON p.profile_id=s.profile_id
                    WHERE s.singleton_id=1"""
                ).fetchone()
                if row is None:
                    row = connection.execute(
                        """SELECT * FROM button_profiles
                        ORDER BY CASE WHEN profile_id=? THEN 0 ELSE 1 END,
                                 name COLLATE NOCASE, profile_id
                        LIMIT 1""",
                        (BUILT_IN_BUTTON_PROFILE_ID,),
                    ).fetchone()
                    if row is None:
                        raise ButtonProfileStorageError("button profile catalog is empty")
                    connection.execute(
                        """INSERT INTO selected_button_profile (singleton_id, profile_id)
                        VALUES (1, ?) ON CONFLICT(singleton_id)
                        DO UPDATE SET profile_id=excluded.profile_id""",
                        (row["profile_id"],),
                    )
                connection.commit()
                return self._from_row(row)
            except ButtonProfileRepositoryError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise ButtonProfileStorageError("could not read selected button profile") from error

    def select_profile(self, profile_id: str, expected_revision: int) -> StoredButtonProfile:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM button_profiles WHERE profile_id=?", (profile_id,)
                ).fetchone()
                if row is None:
                    raise ButtonProfileNotFoundError(profile_id)
                if row["revision"] != expected_revision:
                    raise ButtonProfileRevisionConflictError(
                        profile_id, expected_revision, row["revision"]
                    )
                connection.execute(
                    """INSERT INTO selected_button_profile (singleton_id, profile_id)
                    VALUES (1, ?) ON CONFLICT(singleton_id)
                    DO UPDATE SET profile_id=excluded.profile_id""",
                    (profile_id,),
                )
                connection.commit()
                return self._from_row(row)
            except ButtonProfileRepositoryError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise ButtonProfileStorageError(
                    f"could not select button profile {profile_id}"
                ) from error

    def create_profile(
        self, name: str, definition: ButtonProfileDefinition | None = None
    ) -> StoredButtonProfile:
        validate_button_profile_name(name)
        definition = definition or empty_button_profile_definition()
        timestamp, profile_id = (
            canonical_utc_timestamp(self._clock()),
            str(self._identifier_factory()),
        )
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._insert(
                    connection,
                    StoredButtonProfile(profile_id, name, 1, definition, timestamp, timestamp),
                )
                row = connection.execute(
                    "SELECT * FROM button_profiles WHERE profile_id=?", (profile_id,)
                ).fetchone()
                connection.commit()
                return self._from_row(row)
            except sqlite3.IntegrityError as error:
                connection.rollback()
                if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                    raise ButtonProfileNameConflictError(name) from error
                raise ButtonProfileStorageError("could not create button profile") from error
            except ButtonProfileRepositoryError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise ButtonProfileStorageError("could not create button profile") from error

    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: ButtonProfileDefinition,
    ) -> StoredButtonProfile:
        validate_button_profile_name(name)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        timestamp = canonical_utc_timestamp(self._clock())
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """UPDATE button_profiles SET name=?, revision=revision+1,
                    schema_version=?, definition_json=?, definition_fingerprint=?, updated_at_utc=?
                    WHERE profile_id=? AND revision=?""",
                    (
                        name,
                        definition.schema_version,
                        canonical_button_profile_bytes(definition).decode(),
                        button_profile_fingerprint(definition),
                        timestamp,
                        profile_id,
                        expected_revision,
                    ),
                )
                if cursor.rowcount == 0:
                    row = connection.execute(
                        "SELECT revision FROM button_profiles WHERE profile_id=?", (profile_id,)
                    ).fetchone()
                    connection.rollback()
                    if row is None:
                        raise ButtonProfileNotFoundError(profile_id)
                    raise ButtonProfileRevisionConflictError(
                        profile_id, expected_revision, row["revision"]
                    )
                row = connection.execute(
                    "SELECT * FROM button_profiles WHERE profile_id=?", (profile_id,)
                ).fetchone()
                connection.commit()
                return self._from_row(row)
            except sqlite3.IntegrityError as error:
                connection.rollback()
                if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                    raise ButtonProfileNameConflictError(name) from error
                raise ButtonProfileStorageError("could not update button profile") from error
            except ButtonProfileRepositoryError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise ButtonProfileStorageError(
                    f"could not update button profile {profile_id}"
                ) from error

    def delete_profile(self, profile_id: str, expected_revision: int) -> None:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        with self._connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                if profile_id == BUILT_IN_BUTTON_PROFILE_ID:
                    raise ButtonProfileProtectedError(
                        "the built-in button profile cannot be deleted"
                    )
                selected = connection.execute(
                    "SELECT profile_id FROM selected_button_profile WHERE singleton_id=1"
                ).fetchone()
                if selected is not None and selected["profile_id"] == profile_id:
                    raise ButtonProfileProtectedError(
                        "the selected button profile cannot be deleted"
                    )
                cursor = connection.execute(
                    "DELETE FROM button_profiles WHERE profile_id=? AND revision=?",
                    (profile_id, expected_revision),
                )
                if cursor.rowcount == 0:
                    row = connection.execute(
                        "SELECT revision FROM button_profiles WHERE profile_id=?",
                        (profile_id,),
                    ).fetchone()
                    connection.rollback()
                    if row is None:
                        raise ButtonProfileNotFoundError(profile_id)
                    raise ButtonProfileRevisionConflictError(
                        profile_id, expected_revision, row["revision"]
                    )
                connection.commit()
            except ButtonProfileRepositoryError:
                connection.rollback()
                raise
            except sqlite3.Error as error:
                connection.rollback()
                raise ButtonProfileStorageError(
                    f"could not delete button profile {profile_id}"
                ) from error

    @staticmethod
    def _insert(connection: sqlite3.Connection, profile: StoredButtonProfile) -> None:
        connection.execute(
            "INSERT INTO button_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                profile.profile_id,
                profile.name,
                profile.revision,
                profile.definition.schema_version,
                canonical_button_profile_bytes(profile.definition).decode(),
                button_profile_fingerprint(profile.definition),
                profile.created_at,
                profile.updated_at,
            ),
        )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> StoredButtonProfile:
        profile_id = str(row["profile_id"])
        try:
            raw = row["definition_json"]
            definition = decode_button_profile(json.loads(raw))
            if raw != canonical_button_profile_bytes(definition).decode():
                raise ValueError("definition_json is not canonical")
            if row["schema_version"] != definition.schema_version:
                raise ValueError("schema_version column disagrees")
            if row["definition_fingerprint"] != button_profile_fingerprint(definition):
                raise ValueError("definition fingerprint mismatch")
            return StoredButtonProfile(
                profile_id,
                row["name"],
                row["revision"],
                definition,
                row["created_at_utc"],
                row["updated_at_utc"],
            )
        except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise StoredButtonProfileDataError(profile_id, str(error)) from error
