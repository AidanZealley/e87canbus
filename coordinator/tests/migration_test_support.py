"""Build genuinely older application databases for upgrade tests."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

# Reversals for the schema each migration adds, keyed by the version that added
# it. Rewinding has to undo the schema as well as the history row: replaying a
# migration over a schema that already has its changes is not what an upgrade
# from an older install does, and would hide a genuinely broken migration.
_SCHEMA_REVERSALS: dict[int, Callable[[sqlite3.Connection], None]] = {
    9: lambda connection: connection.execute(
        "ALTER TABLE application_settings DROP COLUMN dashboard_id"
    ),
}


def rewind_application_database(connection: sqlite3.Connection, to_version: int) -> None:
    """Return an initialized database to the state it had at ``to_version``."""

    applied = tuple(
        row[0]
        for row in connection.execute(
            "SELECT version FROM schema_migrations WHERE version > ? ORDER BY version DESC",
            (to_version,),
        ).fetchall()
    )
    for version in applied:
        reverse = _SCHEMA_REVERSALS.get(version)
        if reverse is not None:
            reverse(connection)
    connection.execute("DELETE FROM schema_migrations WHERE version > ?", (to_version,))
