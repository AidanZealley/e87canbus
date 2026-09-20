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

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 3 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/03-persist-device-state.md, all accepted dependency handoffs and linked product documents. Inspect the uncommitted diff and surrounding SQLite migration, connection policy, repositories and app composition. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check upgrade safety, transaction boundaries under concurrent first contact and replacement, exact compare-before-increment behavior, restart durability, identity-role mismatch handling, UTC status receipt time and absence of an event log, cache or generic payload abstraction." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 3 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/03-persist-device-state.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking migration, durability or concurrency defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (review command used, or the subagent fallback that replaced it)
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
