# Workstream 3: Persist device configuration and status

Status: not started.

## Task packet

### Outcome

SQLite durably stores one button-pad configuration envelope and one last-reported status per
authenticated device ID, with atomic generation behavior that later HTTP and SSE handlers can call
directly.

### Scope

- Add one ordered application-database migration for device configuration and last-reported status.
- Add direct SQLite repository methods for get-or-create configuration, replace-if-changed and
  status upsert/read behavior needed by this slice.
- Persist canonical device ID, semantic role, generation, the complete validated role document and
  status receipt time. Reject a stored identity/role mismatch rather than silently reassigning it.
- Use transactions so document comparison, generation increment and replacement are atomic across
  concurrent first contact and publication.
- Store generations as non-negative JSON-safe integers. Do not add a ceiling check: a generation
  advances only when a person edits a button profile, so exhausting the JSON-safe range is not a
  reachable condition and guarding it is untestable ceremony.
- Store receipt time from an injectable coordinator UTC clock. Do not use it as presence, expiry or
  heartbeat state.
- Wire the repository through `create_app` using the existing shared `SqliteApplicationDatabase`
  policy without adding a cache or repository-of-repositories.

### Non-goals

- HTTP routes, SSE subscribers, authenticated-contact inventory, Wi-Fi association or admin queries.
- Event sourcing, replay logs, payload digests, generic transport storage or field-level updates.
- Device-side persistence, status retries or Servotronic configuration/status documents.

### Initial ownership

- `hosts/src/e87canbus/adapters/sqlite_database.py`
- new direct repository module or modules under `hosts/src/e87canbus/adapters/`
- the smallest corresponding data values under `hosts/src/e87canbus/domain/devices/` if needed
- `hosts/src/e87canbus/api/main.py` for repository construction and app-state exposure only
- focused migration and repository tests under `hosts/tests/`

Integration exception: adjust database-version assertions and existing app factory fixtures. Do not
add routes or publisher lifecycle.

### Required seams

- Repository inputs and outputs use the validated Workstream 1 button-pad document, not arbitrary
  bytes, base64, a digest envelope or a transport-neutral event payload.
- First contact accepts the current role-default document and returns the one durable envelope.
  The initial generation is an implementation choice but must be recorded and tested consistently.
- Identical complete documents return the existing envelope without a write or increment.
- A changed document increments exactly once in the same transaction that stores it.
- Status storage records `status_version`, applied generation, nullable configuration error, the
  validated empty button-pad device object and coordinator receipt time.

### Acceptance criteria

- A fresh database migrates and a version-9 database upgrades without losing existing profiles or
  settings.
- First get-or-create, identical replacement, changed replacement and process restart exhibit the
  approved generation behavior.
- Concurrent first contacts cannot create duplicate rows or skip/manufacture a generation.
- A valid status replaces the prior last-reported value and receipt time; no background update or
  expiry occurs.
- Database errors cross the existing persistence error boundary rather than leaking raw SQLite
  exceptions.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_sqlite_profiles.py hosts/tests/test_sqlite_button_profiles.py hosts/tests/test_sqlite_settings.py hosts/tests/test_device_state_repository.py hosts/tests/test_controller_loop.py
uv run mypy
uv run ruff check hosts
uv run lint-imports
git diff --check
```

The implementation agent creates `hosts/tests/test_device_state_repository.py`.

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 3 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/03-persist-device-state.md, all accepted dependency handoffs and linked product documents. Inspect the uncommitted diff and surrounding SQLite migration, connection policy, repositories and app composition. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check upgrade safety, transaction boundaries under concurrent first contact and replacement, exact compare-before-increment behavior, restart durability, identity-role mismatch handling, UTC status receipt time and absence of an event log, cache or generic payload abstraction.
```

Closure review:

```text
Perform the focused closure review for Workstream 3 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/03-persist-device-state.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking migration, durability or concurrency defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `fd20e1eed53659c7a851160c1a44e12bcf843ac3`
- Outcome: Migration 10 stores one complete button-pad configuration and one last status per canonical device ID. The repository serializes first contact and compare-before-replace with `BEGIN IMMEDIATE`; changed documents advance the durable generation once. Status stores the validated empty device object and a coordinator UTC receipt time.
- Files changed: `hosts/src/e87canbus/adapters/sqlite_database.py`, `hosts/src/e87canbus/adapters/sqlite_device_state.py`, `hosts/src/e87canbus/api/main.py`, `hosts/tests/migration_test_support.py`, `hosts/tests/test_device_state_repository.py`.
- Decisions: Initial generation is 0. Repository methods take the validated `ButtonPadScene` and `ButtonPadStatus` models. A mismatched stored role raises `DeviceRoleMismatchError`; SQLite failures raise `DeviceStateStorageError`. The app exposes the direct repository on `app.state.device_state_repository`. No publication or routes were added.
- Verification: The targeted pytest command passed (72 tests). `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports` and `git diff --check` passed. Tests cover version-9 upgrade with retained profile and settings, restart durability, concurrent first contact and replacement, status overwrite and UTC receipt time, role mismatch, and the persistence error boundary. The deletion and simplification pass found no duplicate state or obsolete path to remove.
- Known limitations or external checks: None for this simulated slice.
- Specification drift: None.

## Independent review

- Reviewer: Fresh independent review agent.
- Verdict: Approved. Migration 10 and the direct repository meet this workstream's persistence contract.
- Required findings: None. Migration 10 adds separate current configuration and last-status tables without altering profiles or settings. `BEGIN IMMEDIATE` covers role checks, first insertion, complete-document comparison, generation increment and replacement, so concurrent callers serialize around the same row. An equal validated scene returns the stored envelope without an update. The configuration and status rows survive a new repository instance. Both reads and writes reject a role recorded in either table that conflicts with the authenticated role. SQLite failures cross the `DeviceStateStorageError` boundary.
- Optional observations: `upsert_status` samples its UTC clock before acquiring the write transaction. Concurrent status requests can therefore commit in a different order from their sampled timestamps, leaving the last stored status with an earlier receipt time than the value it replaced. The contract does not require timestamp ordering, and each stored timestamp remains a valid coordinator receipt time.
- Questions: None.

Review evidence: Read the accepted Workstream 1 and 2 handoffs, the Slice 02 and linked device contracts, the migration and shared connection policy, repository, app construction, and focused tests. The version-9 upgrade test retains an edited profile and settings; the repository tests cover restart, simultaneous first contacts and equal replacements, role mismatch, status overwrite and injected UTC time. The focused persistence suite passed (62 tests). `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports` and `git diff --check` passed. The diff adds no event log, cache or generic payload store.

## Resolution

- Finding dispositions: No Required findings. The receipt-time ordering observation remains Optional because the contract records when the coordinator received each status and does not order concurrent requests by timestamp.
- Simplification/deletion pass: The implementation pass found no duplicate state or obsolete path. Review found no event log, cache or generic payload abstraction to remove.
- Final verification: The implementation's 72 targeted tests, mypy, Ruff, import checks and diff check passed. Independent review passed its 62 focused tests and static checks. Closure review passed the 7 repository tests and diff check, with no remaining Required findings.

## Closure review

- Verdict: Approved. The independent review accepted no Required findings, so no remediation fix needed closure verification.
- Remaining required findings: None. Migration 10 runs inside the existing exclusive initialization transaction and leaves profile and settings tables intact. Configuration creation and replacement hold `BEGIN IMMEDIATE` through the role check, comparison, write and commit. The focused repository tests passed (7 tests), including upgrade, restart durability and concurrent first contact and replacement. `git diff --check` passed.
