"""SQLite persistence for complete, revisioned steering profiles."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Never, cast
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    BUILT_IN_PROFILE_ID as BUILT_IN_PROFILE_ID,
)
from e87canbus.adapters.sqlite_database import (
    BUILT_IN_PROFILE_NAME as BUILT_IN_PROFILE_NAME,
)
from e87canbus.adapters.sqlite_database import (
    CURRENT_MIGRATION_VERSION as CURRENT_MIGRATION_VERSION,
)
from e87canbus.adapters.sqlite_database import (
    ApplicationDatabaseError,
    SqliteApplicationDatabase,
    UnsupportedDatabaseVersionError,
)
from e87canbus.features.profile_repository import (
    ProfileNameConflictError,
    ProfileNotFoundError,
    ProfileRevisionConflictError,
    SteeringProfileRepositoryError,
    SteeringProfileStorageError,
    StoredProfileDataError,
)
from e87canbus.features.steering import (
    SteeringCurveDefinition,
    SteeringCurvePoint,
    StoredSteeringProfile,
    canonical_steering_curve_bytes,
    steering_curve_fingerprint,
    validate_steering_curve_definition,
    validate_steering_profile_name,
)
from e87canbus.features.timestamps import canonical_utc_timestamp


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SqliteSteeringProfileRepository:
    """File-backed repository using one short-lived SQLite connection per operation."""

    def __init__(
        self,
        database_path: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = _utc_now,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
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
            raise
        except ApplicationDatabaseError as error:
            raise SteeringProfileStorageError(
                "could not initialize the application database"
            ) from error

    def list_profiles(self) -> tuple[StoredSteeringProfile, ...]:
        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT * FROM steering_profiles
                ORDER BY name COLLATE NOCASE, profile_id
                """
            ).fetchall()
            return tuple(self._profile_from_row(row) for row in rows)
        except SteeringProfileRepositoryError:
            raise
        except sqlite3.Error as error:
            raise SteeringProfileStorageError("could not list steering profiles") from error
        finally:
            connection.close()

    def get_profile(self, profile_id: str) -> StoredSteeringProfile | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM steering_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
            return None if row is None else self._profile_from_row(row)
        except SteeringProfileRepositoryError:
            raise
        except sqlite3.Error as error:
            raise SteeringProfileStorageError(
                f"could not read steering profile {profile_id}"
            ) from error
        finally:
            connection.close()

    def create_profile(
        self, name: str, definition: SteeringCurveDefinition
    ) -> StoredSteeringProfile:
        validate_steering_profile_name(name)
        validate_steering_curve_definition(definition)
        profile_id = str(self._identifier_factory())
        timestamp = canonical_utc_timestamp(self._clock())
        profile = StoredSteeringProfile(
            profile_id=profile_id,
            name=name,
            revision=1,
            definition=definition,
            created_at=timestamp,
            updated_at=timestamp,
        )
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_profile(connection, profile)
            row = self._required_row(connection, profile_id)
            stored = self._profile_from_row(row)
            connection.commit()
            return stored
        except sqlite3.IntegrityError as error:
            connection.rollback()
            self._raise_integrity_error(
                name, "could not create steering profile", error
            )
        except SteeringProfileRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise SteeringProfileStorageError("could not create steering profile") from error
        finally:
            connection.close()

    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: SteeringCurveDefinition,
    ) -> StoredSteeringProfile:
        validate_steering_profile_name(name)
        validate_steering_curve_definition(definition)
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        timestamp = canonical_utc_timestamp(self._clock())
        definition_json = canonical_steering_curve_bytes(definition).decode("utf-8")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE steering_profiles
                SET name = ?, revision = revision + 1, schema_version = ?,
                    definition_json = ?, definition_fingerprint = ?,
                    updated_at_utc = ?
                WHERE profile_id = ? AND revision = ?
                """,
                (
                    name,
                    definition.schema_version,
                    definition_json,
                    steering_curve_fingerprint(definition),
                    timestamp,
                    profile_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount == 0:
                actual_revision = self._revision_for(connection, profile_id)
                connection.rollback()
                if actual_revision is None:
                    raise ProfileNotFoundError(profile_id)
                raise ProfileRevisionConflictError(
                    profile_id, expected_revision, actual_revision
                )
            row = self._required_row(connection, profile_id)
            stored = self._profile_from_row(row)
            connection.commit()
            return stored
        except sqlite3.IntegrityError as error:
            connection.rollback()
            self._raise_integrity_error(
                name,
                f"could not update steering profile {profile_id}",
                error,
            )
        except SteeringProfileRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise SteeringProfileStorageError(
                f"could not update steering profile {profile_id}"
            ) from error
        finally:
            connection.close()

    def delete_profile(self, profile_id: str, expected_revision: int) -> None:
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "DELETE FROM steering_profiles WHERE profile_id = ? AND revision = ?",
                (profile_id, expected_revision),
            )
            if cursor.rowcount == 0:
                actual_revision = self._revision_for(connection, profile_id)
                connection.rollback()
                if actual_revision is None:
                    raise ProfileNotFoundError(profile_id)
                raise ProfileRevisionConflictError(
                    profile_id, expected_revision, actual_revision
                )
            connection.commit()
        except SteeringProfileRepositoryError:
            connection.rollback()
            raise
        except sqlite3.Error as error:
            connection.rollback()
            raise SteeringProfileStorageError(
                f"could not delete steering profile {profile_id}"
            ) from error
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        try:
            return self._database.connect()
        except ApplicationDatabaseError as error:
            raise SteeringProfileStorageError(
                "could not open the steering profile database"
            ) from error

    @staticmethod
    def _insert_profile(
        connection: sqlite3.Connection, profile: StoredSteeringProfile
    ) -> None:
        definition_json = canonical_steering_curve_bytes(profile.definition).decode("utf-8")
        connection.execute(
            """
            INSERT INTO steering_profiles (
                profile_id, name, revision, schema_version,
                definition_json, definition_fingerprint, created_at_utc, updated_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.profile_id,
                profile.name,
                profile.revision,
                profile.definition.schema_version,
                definition_json,
                steering_curve_fingerprint(profile.definition),
                profile.created_at,
                profile.updated_at,
            ),
        )

    @staticmethod
    def _profile_from_row(row: sqlite3.Row) -> StoredSteeringProfile:
        profile_id = str(row["profile_id"])
        try:
            definition_json = row["definition_json"]
            if not isinstance(definition_json, str):
                raise ValueError("definition_json must be text")
            value = json.loads(definition_json)
            if not isinstance(value, dict) or set(value) != {
                "schema_version",
                "points",
            }:
                raise ValueError("definition_json has unexpected fields")
            raw_points = value["points"]
            if not isinstance(raw_points, list):
                raise ValueError("definition points must be a list")
            points: list[SteeringCurvePoint] = []
            for raw_point in raw_points:
                if not isinstance(raw_point, dict) or set(raw_point) != {
                    "speed_deci_kph",
                    "assistance_per_mille",
                }:
                    raise ValueError("definition point has unexpected fields")
                points.append(
                    SteeringCurvePoint(
                        speed_deci_kph=raw_point["speed_deci_kph"],
                        assistance_per_mille=raw_point["assistance_per_mille"],
                    )
                )
            definition = SteeringCurveDefinition(
                schema_version=value["schema_version"],
                points=tuple(points),
            )
            if row["schema_version"] != definition.schema_version:
                raise ValueError("schema_version column disagrees with definition_json")
            canonical_json = canonical_steering_curve_bytes(definition).decode("utf-8")
            if definition_json != canonical_json:
                raise ValueError("definition_json is not canonical")
            fingerprint = steering_curve_fingerprint(definition)
            if row["definition_fingerprint"] != fingerprint:
                raise ValueError("definition fingerprint mismatch")
            return StoredSteeringProfile(
                profile_id=profile_id,
                name=row["name"],
                revision=row["revision"],
                definition=definition,
                created_at=row["created_at_utc"],
                updated_at=row["updated_at_utc"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StoredProfileDataError(profile_id, str(error)) from error

    @staticmethod
    def _required_row(connection: sqlite3.Connection, profile_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM steering_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if row is None:
            raise SteeringProfileStorageError(
                f"committed steering profile row disappeared: {profile_id}"
            )
        return cast(sqlite3.Row, row)

    @staticmethod
    def _revision_for(connection: sqlite3.Connection, profile_id: str) -> int | None:
        row = connection.execute(
            "SELECT revision FROM steering_profiles WHERE profile_id = ?", (profile_id,)
        ).fetchone()
        if row is None:
            return None
        revision = row["revision"]
        if type(revision) is not int or revision < 1:
            raise StoredProfileDataError(profile_id, "revision must be a positive integer")
        return revision

    @staticmethod
    def _raise_integrity_error(
        name: str,
        fallback_message: str,
        error: sqlite3.IntegrityError,
    ) -> Never:
        # The schema's only UNIQUE constraint is the case-insensitive profile name.
        # The profile ID uses a PRIMARY KEY constraint with a distinct extended error code.
        if error.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE:
            raise ProfileNameConflictError(name) from error
        raise SteeringProfileStorageError(fallback_message) from error
