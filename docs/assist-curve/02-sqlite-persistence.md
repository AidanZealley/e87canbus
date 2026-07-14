# Phase 2: SQLite profile persistence

## Goal

Persist named, revisioned steering profiles in a local SQLite database owned by the coordinator
process. Provide a repository interface that can be tested without FastAPI or the runtime kernel.

This phase stores profiles; it does not activate them or expose HTTP endpoints.

## Storage ownership

- SQLite is an adapter behind a domain-facing repository protocol.
- The browser and steering calculation never open the database.
- Database I/O occurs outside pure transitions and outside the CAN reader threads.
- Use Python's standard `sqlite3` module unless requirements emerge that justify an ORM.
- Configure the database path through composition. Tests use a temporary file, not the deployment
  database.

Suggested repository operations:

```python
class SteeringProfileRepository(Protocol):
    def list_profiles(self) -> tuple[StoredSteeringProfile, ...]: ...
    def get_profile(self, profile_id: str) -> StoredSteeringProfile | None: ...
    def create_profile(self, name: str, definition: SteeringCurveDefinition) -> StoredSteeringProfile: ...
    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: SteeringCurveDefinition,
    ) -> StoredSteeringProfile: ...
    def delete_profile(self, profile_id: str, expected_revision: int) -> None: ...
```

Use typed domain exceptions for not found, revision conflict and name conflict. Do not make callers
interpret SQLite exception strings.

## Schema

Keep the definition as canonical JSON text in one profile row. The data set is tiny and profiles
are loaded as complete aggregates, so a normalized point table would add joins and partial-update
states without a useful query benefit.

Suggested initial schema:

```sql
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
```

Store the schema and interpolation columns redundantly with the JSON to support inspection and
migration. On read, verify that columns, decoded definition and fingerprint agree. Corrupt or
unsupported rows must produce an explicit error rather than a partial profile.

Do not store current runtime `active` state in this table. A later startup-selection setting can
refer to a saved profile, but the active definition itself belongs to the runtime owner and may be
unsaved.

## Migrations and initialization

- Run numbered, idempotence-aware migrations under an exclusive initialization transaction.
- Refuse to run against a database whose migration version is newer than the code supports.
- Seed the built-in profile only when the profile table is empty.
- Give the seed a stable ID if deployments/tests need to refer to it; otherwise record it through a
  separate startup-selection setting rather than relying on its name.
- Never replace a user-edited profile merely because its name matches the built-in default.

Database initialization should be explicit in application startup, not a side effect of importing
a module.

## Revision and transaction behavior

Create starts at revision 1. Update executes one conditional statement equivalent to:

```sql
UPDATE steering_profiles
SET name = ?, revision = revision + 1, definition_json = ?, ...
WHERE profile_id = ? AND revision = ?;
```

Zero affected rows must be distinguished as not-found versus revision-conflict before returning a
typed error. Delete uses the same expected-revision rule.

Each create, update or delete is one transaction. Generate timestamps once per operation. Return
the committed row rather than reconstructing a possibly different result in the API layer.

Use one clearly owned connection per execution context or serialize repository access. Do not turn
off SQLite thread checks and share an unsynchronized connection between the FastAPI owner and live
runtime threads.

## Durability and write frequency

- Commit only explicit create, save, rename and delete actions.
- Pointer movement and Apply-without-Save never write SQLite.
- Keep SQLite durability settings explicit and conservative for the deployment filesystem.
- SQLite protects database transaction structure; it does not replace stable vehicle power,
  storage health monitoring or backups.

## Tests

Test with a real temporary SQLite file:

- Fresh migration and repeat startup.
- Built-in seed behavior.
- Create/get/list ordering and case-insensitive name uniqueness.
- Update increments exactly one revision.
- Stale update and stale delete conflicts.
- Delete of a missing profile.
- Full definition and integer-unit round trip.
- Fingerprint mismatch or malformed JSON fails closed.
- Unsupported future schema/interpolation fails closed.
- Transaction rollback on injected failure.
- Database with a newer migration version is rejected.
- Reopening the connection retains profiles.

Repository contract tests should be reusable if an in-memory fake is introduced for API tests.

## Completion criteria

- Saved profiles survive process and connection restart.
- Updates cannot silently overwrite a newer revision.
- Domain validation runs on both writes and reads.
- SQLite types and exceptions do not escape the adapter.
- No runtime activation behavior has been added implicitly.
