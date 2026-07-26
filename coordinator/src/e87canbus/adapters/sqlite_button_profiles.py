"""SQLite persistence for button-pad profiles."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import assert_never
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    BUILT_IN_BUTTON_PROFILE_ID,
    SqliteApplicationDatabase,
)
from e87canbus.adapters.sqlite_revisioned_profiles import (
    ProfileMigration,
    RevisionedProfileSpec,
    SqliteRevisionedProfileRepository,
    utc_now,
)
from e87canbus.domain.buttons.catalogue import ButtonCommand
from e87canbus.domain.buttons.commands import decode_button_command
from e87canbus.domain.buttons.profiles import (
    BUTTON_PROFILE_SCHEMA_VERSION,
    ButtonProfileDefinition,
    ButtonSlot,
    StoredButtonProfile,
    button_profile_fingerprint,
    canonical_button_profile_bytes,
    decode_button_profile,
    empty_button_profile_definition,
    validate_button_profile_name,
)
from e87canbus.domain.buttons.repository import BUTTON_PROFILE_KIND
from e87canbus.domain.events import RGB_BLUE, RGB_WHITE, Rgb
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
    ProfileNotFoundError,
    ProfileProtectedError,
    ProfileRevisionConflictError,
    ProfileStorageError,
    validate_expected_revision,
)

BUTTON_PROFILE_V1_SCHEMA_VERSION = 1


def _v1_seed_colour(command: ButtonCommand) -> Rgb:
    """The colour v1 derived for this command, which becomes its authored base colour.

    This reproduces the ``ButtonCommandPresentation`` table as it stood at v1 rather than
    reading today's, deliberately: a migration describes rows that were written in the
    past, so it must not move when the live derivation does. A pad upgraded through it
    looks exactly as it did, except for the accepted steering-mode regression - those
    buttons were bright blue in automatic and bright amber in manual, and become one blue
    that is bright only in automatic.
    """

    match command:
        case SelectSteeringMode() | ToggleAutomaticAssistance():
            return RGB_BLUE
        case (
            AdjustManualAssistance()
            | SetManualAssistanceLevel()
            | SetMaximumAssistance()
            | ToggleMaximumAssistance()
            | StartHighBeamStrobe()
        ):
            return RGB_WHITE
        case _:
            assert_never(command)


def migrate_button_profile(
    stored_version: int, definition_json: str, fingerprint: str
) -> ButtonProfileDefinition:
    """Read a definition written before slots carried presentation.

    A v1 slot was the bare command, so the colour it is given here is the one v1 would
    have shown it in, and both authored fields it never had stay null. Migration happens
    on read; the row itself is rewritten at the current version by the next save.

    The row is verified before it is upgraded, so an old row fails as closed as a current
    one. v1's canonical encoding was the same sorted, separator-free JSON this build
    writes, applied to the v1 payload, so re-encoding what was parsed reproduces exactly
    what v1 would have stored - no v1 decoder has to be kept alive to check it.
    """

    if stored_version != BUTTON_PROFILE_V1_SCHEMA_VERSION:
        raise ValueError(f"unsupported stored button profile schema_version: {stored_version}")
    value = json.loads(definition_json)
    if not isinstance(value, dict) or set(value) != {"schema_version", "slots"}:
        raise ValueError("definition has unexpected fields")
    if value["schema_version"] != stored_version:
        raise ValueError("schema_version column disagrees with definition_json")
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if definition_json != canonical.decode():
        raise ValueError("definition_json is not canonical")
    if fingerprint != sha256(canonical).hexdigest():
        raise ValueError("definition fingerprint mismatch")
    slots = value["slots"]
    if not isinstance(slots, list):
        raise ValueError("slots must be a list")
    return ButtonProfileDefinition(
        BUTTON_PROFILE_SCHEMA_VERSION,
        tuple(None if command is None else _migrated_slot(command) for command in slots),
    )


def _migrated_slot(command_json: object) -> ButtonSlot:
    command = decode_button_command(command_json)
    return ButtonSlot(command, _v1_seed_colour(command))


BUTTON_PROFILE_SPEC = RevisionedProfileSpec[ButtonProfileDefinition, StoredButtonProfile](
    kind=BUTTON_PROFILE_KIND,
    table="button_profiles",
    encode=canonical_button_profile_bytes,
    decode=decode_button_profile,
    fingerprint=button_profile_fingerprint,
    validate_name=validate_button_profile_name,
    build=StoredButtonProfile,
    migration=ProfileMigration(BUTTON_PROFILE_SCHEMA_VERSION, migrate_button_profile),
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
