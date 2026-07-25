"""One SQLite mechanism for every revisioned profile table.

Steering curves and button-pad mappings are stored identically: a named row carrying a
monotonic ``revision``, the definition as canonical JSON, and a content fingerprint that
lets a corrupt row fail closed. Only the table name and the definition codec differ, so
they are parameters here rather than a second copy of the same 350 lines.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Generic, Protocol, TypeVar, cast
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    ApplicationDatabaseError,
    SqliteApplicationDatabase,
    UnsupportedDatabaseVersionError,
)
from e87canbus.domain.revisioned_profiles import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRepositoryError,
    ProfileRevisionConflictError,
    ProfileStorageError,
    StoredProfileDataError,
    validate_expected_revision,
)
from e87canbus.domain.timestamps import canonical_utc_timestamp


class ProfileDefinition(Protocol):
    """Any versioned definition whose schema version is mirrored in its own column."""

    @property
    def schema_version(self) -> int: ...


DefinitionT = TypeVar("DefinitionT", bound=ProfileDefinition)
StoredT = TypeVar("StoredT")


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class RevisionedProfileSpec(Generic[DefinitionT, StoredT]):
    """Everything that distinguishes one revisioned profile table from another."""

    kind: str
    table: str
    encode: Callable[[DefinitionT], bytes]
    decode: Callable[[object], DefinitionT]
    fingerprint: Callable[[DefinitionT], str]
    validate_name: Callable[[str], None]
    build: Callable[[str, str, int, DefinitionT, str, str], StoredT]

    def __post_init__(self) -> None:
        if not self.kind or self.kind != self.kind.strip():
            raise ValueError("kind must be non-empty trimmed text")
        # The table name is interpolated into SQL, so only ever accept a bare identifier.
        if not self.table.isidentifier():
            raise ValueError("table must be a bare SQL identifier")


class SqliteRevisionedProfileRepository(Generic[DefinitionT, StoredT]):
    """File-backed repository using one short-lived SQLite connection per operation.

    Every method closes its connection in ``finally``. ``sqlite3``'s connection context
    manager only ends the *transaction*, so a connection left for the garbage collector
    keeps its WAL read lock alive for as long as a traceback retains the frame; combined
    with the ``BEGIN IMMEDIATE`` writers below that surfaces as ``SQLITE_BUSY`` once an
    exception has propagated out to an HTTP handler.
    """

    def __init__(
        self,
        spec: RevisionedProfileSpec[DefinitionT, StoredT],
        database_path: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = utc_now,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._spec = spec
        self._database = (
            database_path
            if isinstance(database_path, SqliteApplicationDatabase)
            else SqliteApplicationDatabase(database_path, clock=clock)
        )
        self._clock = clock
        self._identifier_factory = identifier_factory

    def initialize(self) -> None:
        """Compatibility delegate to the shared application database owner."""

        try:
            self._database.initialize()
        except UnsupportedDatabaseVersionError:
            # A newer on-disk schema is a deployment fact, not a storage malfunction.
            raise
        except ApplicationDatabaseError as error:
            raise ProfileStorageError("could not initialize the application database") from error

    def list_profiles(self) -> tuple[StoredT, ...]:
        with self._reading(f"could not list {self._spec.kind}s") as connection:
            rows = connection.execute(
                f"SELECT * FROM {self._spec.table} ORDER BY name COLLATE NOCASE, profile_id"
            ).fetchall()
            return tuple(self._from_row(row) for row in rows)

    def get_profile(self, profile_id: str) -> StoredT | None:
        with self._reading(f"could not read {self._spec.kind} {profile_id}") as connection:
            row = self._row_for(connection, profile_id)
            return None if row is None else self._from_row(row)

    def create_profile(self, name: str, definition: DefinitionT) -> StoredT:
        self._spec.validate_name(name)
        # Encode before opening the connection: a rejected definition must never leave a
        # write transaction open behind it.
        encoded = self._encoded(definition)
        profile_id, timestamp = str(self._identifier_factory()), self._timestamp()
        with self._writing(f"could not create {self._spec.kind}", name=name) as connection:
            connection.execute(
                f"""INSERT INTO {self._spec.table} (
                    profile_id, name, revision, schema_version,
                    definition_json, definition_fingerprint, created_at_utc, updated_at_utc
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)""",
                (profile_id, name, definition.schema_version, *encoded, timestamp, timestamp),
            )
            return self._from_row(self._required_row(connection, profile_id))

    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: DefinitionT,
    ) -> StoredT:
        self._spec.validate_name(name)
        validate_expected_revision(expected_revision)
        encoded = self._encoded(definition)
        timestamp = self._timestamp()
        failure = f"could not update {self._spec.kind} {profile_id}"
        with self._writing(failure, name=name) as connection:
            cursor = connection.execute(
                f"""UPDATE {self._spec.table}
                SET name = ?, revision = revision + 1, schema_version = ?,
                    definition_json = ?, definition_fingerprint = ?, updated_at_utc = ?
                WHERE profile_id = ? AND revision = ?""",
                (
                    name,
                    definition.schema_version,
                    *encoded,
                    timestamp,
                    profile_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount == 0:
                raise self._stale_write(connection, profile_id, expected_revision)
            return self._from_row(self._required_row(connection, profile_id))

    def delete_profile(self, profile_id: str, expected_revision: int) -> None:
        validate_expected_revision(expected_revision)
        with self._writing(f"could not delete {self._spec.kind} {profile_id}") as connection:
            self._check_deletable(connection, profile_id)
            cursor = connection.execute(
                f"DELETE FROM {self._spec.table} WHERE profile_id = ? AND revision = ?",
                (profile_id, expected_revision),
            )
            if cursor.rowcount == 0:
                raise self._stale_write(connection, profile_id, expected_revision)

    def _check_deletable(self, connection: sqlite3.Connection, profile_id: str) -> None:
        """Hook for tables whose rows can be pinned by other state; open by default."""

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._database.connect()
        except ApplicationDatabaseError as error:
            raise ProfileStorageError(f"could not open the {self._spec.kind} database") from error

    @contextmanager
    def _reading(self, failure: str) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        except ProfileRepositoryError:
            raise
        except sqlite3.Error as error:
            raise ProfileStorageError(failure) from error
        finally:
            connection.close()

    @contextmanager
    def _writing(self, failure: str, *, name: str | None = None) -> Iterator[sqlite3.Connection]:
        """Run the body inside one ``BEGIN IMMEDIATE`` transaction, committing on success."""

        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            # The schema's only UNIQUE constraint is the case-insensitive profile name;
            # the profile ID is a PRIMARY KEY with a distinct extended error code.
            if name is not None and error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
                raise ProfileNameConflictError(self._spec.kind, name) from error
            raise ProfileStorageError(failure) from error
        except ProfileRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise ProfileStorageError(failure) from error
        finally:
            connection.close()

    def _timestamp(self) -> str:
        return canonical_utc_timestamp(self._clock())

    def _encoded(self, definition: DefinitionT) -> tuple[str, str]:
        """Return the canonical JSON text and its fingerprint, in column order."""

        return (
            self._spec.encode(definition).decode("utf-8"),
            self._spec.fingerprint(definition),
        )

    def _row_for(self, connection: sqlite3.Connection, profile_id: str) -> sqlite3.Row | None:
        row = connection.execute(
            f"SELECT * FROM {self._spec.table} WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _required_row(self, connection: sqlite3.Connection, profile_id: str) -> sqlite3.Row:
        row = self._row_for(connection, profile_id)
        if row is None:
            raise ProfileStorageError(f"committed {self._spec.kind} row disappeared: {profile_id}")
        return row

    def _stale_write(
        self, connection: sqlite3.Connection, profile_id: str, expected_revision: int
    ) -> ProfileRepositoryError:
        """Explain why a revision-guarded write matched no row: missing, or moved on."""

        actual_revision = self._revision_for(connection, profile_id)
        if actual_revision is None:
            return ProfileNotFoundError(self._spec.kind, profile_id)
        return ProfileRevisionConflictError(
            self._spec.kind, profile_id, expected_revision, actual_revision
        )

    def _revision_for(self, connection: sqlite3.Connection, profile_id: str) -> int | None:
        row = connection.execute(
            f"SELECT revision FROM {self._spec.table} WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if row is None:
            return None
        revision = row["revision"]
        if type(revision) is not int or revision < 1:
            raise StoredProfileDataError(
                self._spec.kind, profile_id, "revision must be a positive integer"
            )
        return revision

    def _from_row(self, row: sqlite3.Row) -> StoredT:
        profile_id = str(row["profile_id"])
        try:
            definition_json = row["definition_json"]
            if not isinstance(definition_json, str):
                raise ValueError("definition_json must be text")
            definition = self._spec.decode(json.loads(definition_json))
            if row["schema_version"] != definition.schema_version:
                raise ValueError("schema_version column disagrees with definition_json")
            canonical_json, fingerprint = self._encoded(definition)
            if definition_json != canonical_json:
                raise ValueError("definition_json is not canonical")
            if row["definition_fingerprint"] != fingerprint:
                raise ValueError("definition fingerprint mismatch")
            return self._spec.build(
                profile_id,
                row["name"],
                row["revision"],
                definition,
                row["created_at_utc"],
                row["updated_at_utc"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StoredProfileDataError(self._spec.kind, profile_id, str(error)) from error
