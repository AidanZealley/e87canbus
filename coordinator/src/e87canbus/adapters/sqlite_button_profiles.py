"""SQLite persistence for button-pad profiles."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    BUILT_IN_BUTTON_PROFILE_ID,
    SqliteApplicationDatabase,
)
from e87canbus.adapters.sqlite_revisioned_profiles import (
    RevisionedProfileSpec,
    SqliteRevisionedProfileRepository,
    utc_now,
)
from e87canbus.domain.buttons.profiles import (
    ButtonProfileDefinition,
    StoredButtonProfile,
    button_profile_fingerprint,
    canonical_button_profile_bytes,
    decode_button_profile,
    empty_button_profile_definition,
    validate_button_profile_name,
)
from e87canbus.domain.buttons.repository import BUTTON_PROFILE_KIND
from e87canbus.domain.revisioned_profiles import (
    ProfileNotFoundError,
    ProfileProtectedError,
    ProfileRevisionConflictError,
    ProfileStorageError,
    validate_expected_revision,
)

BUTTON_PROFILE_SPEC = RevisionedProfileSpec[ButtonProfileDefinition, StoredButtonProfile](
    kind=BUTTON_PROFILE_KIND,
    table="button_profiles",
    encode=canonical_button_profile_bytes,
    decode=decode_button_profile,
    fingerprint=button_profile_fingerprint,
    validate_name=validate_button_profile_name,
    build=StoredButtonProfile,
)

_UPSERT_SELECTION = """INSERT INTO selected_button_profile (singleton_id, profile_id)
    VALUES (1, ?) ON CONFLICT(singleton_id) DO UPDATE SET profile_id=excluded.profile_id"""


class SqliteButtonProfileRepository(
    SqliteRevisionedProfileRepository[ButtonProfileDefinition, StoredButtonProfile]
):
    """The shared revisioned-profile mechanism plus the single selected-profile pointer.

    Only the selection singleton is button-specific: it makes one profile durable across
    restarts, which is why the selected row (and the built-in fallback) cannot be deleted.
    """

    def __init__(
        self,
        database_path: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = utc_now,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        super().__init__(
            BUTTON_PROFILE_SPEC,
            database_path,
            clock=clock,
            identifier_factory=identifier_factory,
        )

    def create_profile(
        self, name: str, definition: ButtonProfileDefinition | None = None
    ) -> StoredButtonProfile:
        """Create a profile, defaulting to an all-unbound pad the operator can fill in."""

        return super().create_profile(name, definition or empty_button_profile_definition())

    def get_selected_profile(self) -> StoredButtonProfile:
        """Return the selected row, repairing a missing singleton deterministically."""

        with self._writing("could not read selected button profile") as connection:
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
                    raise ProfileStorageError("button profile catalog is empty")
                connection.execute(_UPSERT_SELECTION, (row["profile_id"],))
            return self._from_row(row)

    def select_profile(self, profile_id: str, expected_revision: int) -> StoredButtonProfile:
        validate_expected_revision(expected_revision)
        with self._writing(f"could not select button profile {profile_id}") as connection:
            row = self._row_for(connection, profile_id)
            if row is None:
                raise ProfileNotFoundError(BUTTON_PROFILE_KIND, profile_id)
            if row["revision"] != expected_revision:
                raise ProfileRevisionConflictError(
                    BUTTON_PROFILE_KIND, profile_id, expected_revision, row["revision"]
                )
            connection.execute(_UPSERT_SELECTION, (profile_id,))
            return self._from_row(row)

    def _check_deletable(self, connection: sqlite3.Connection, profile_id: str) -> None:
        """Refuse to remove a profile the runtime still depends on being able to load."""

        if profile_id == BUILT_IN_BUTTON_PROFILE_ID:
            raise ProfileProtectedError("the built-in button profile cannot be deleted")
        selected = connection.execute(
            "SELECT profile_id FROM selected_button_profile WHERE singleton_id=1"
        ).fetchone()
        if selected is not None and selected["profile_id"] == profile_id:
            raise ProfileProtectedError("the selected button profile cannot be deleted")
