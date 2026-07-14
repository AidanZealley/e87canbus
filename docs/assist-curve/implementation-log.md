# Assistance curve implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, important decisions, verification evidence and unresolved issues. It is not a transcript
of commands or a replacement for commit history.

## How to use this log

- Read the roadmap, current phase document, relevant ADRs and all earlier entries before starting.
- Append an entry when a phase or meaningful slice is completed, deliberately deferred or blocked.
- Keep entries concise and factual. Link files and tests instead of pasting large code excerpts.
- Do not rewrite earlier entries to make later decisions look inevitable. Add a correcting entry.
- Record deviations from the phase document and why they were necessary.
- Record new dependencies, migrations and compatibility consequences explicitly.
- Never claim physical validation from simulator or software-only results.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Profile domain model | Verified | 2026-07-14 | Version-1 integer curve contract implemented |
| 2 — SQLite persistence | Verified | 2026-07-14 | Durable catalog and optimistic revisions implemented |
| 3 — Runtime activation | Verified | 2026-07-14 | Ordered in-memory hot activation implemented |
| 4 — Profile API | Verified | 2026-07-14 | CRUD, activation and publication contracts implemented |
| 5 — Interactive editor | Implemented | 2026-07-14 | Automated and selected browser checks pass; touch/pointer verification remains |
| 6 — Smooth interpolation | Not started | — | — |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass; use `Verified` only after every phase
completion criterion and the relevant repository-wide checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The slice of the phase attempted.
- **Changed:** Important files and externally visible behavior.
- **Decisions:** Material choices or deviations, with reasons.
- **Verification:** Exact tests/checks run and their outcome.
- **Documentation:** README/design/API documents updated.
- **Dependencies/migrations:** None, or list additions and operational impact.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-14 — Phase 5: interactive curve editor implemented

- **Status:** Implemented
- **Scope:** Added the shared simulator settings editor for the fixed version-1 curve, including
  draft editing, runtime Apply and saved-profile CRUD. Smooth interpolation, controller transport
  and physical output authority remain outside this phase.
- **Changed:** Added typed steering API requests and errors; active-curve and profile-catalog
  WebSocket integration; an explicit draft/active/saved editor state; a Recharts `linear-v1`
  comparison chart with pointer-captured vertical handles, keyboard sliders and numeric inputs;
  current-speed active/draft readouts; inline revert/delete confirmation; pending-action guards;
  and conflict recovery that retains the draft. Catalog invalidation refetches saved profiles while
  reconnect snapshots update authoritative active state without replacing a dirty draft. Form
  controls use the project's shadcn Input, Label, Select and Button primitives with 44-pixel minimum
  targets.
- **Decisions:** The editor consumes the complete active projection already carried by simulator
  snapshots rather than issuing a duplicate curve-state query. Apply includes saved provenance only
  when the draft exactly matches the selected saved revision. Confirmation is inline so it does not
  cover a point being edited. The existing built-in values remain displayable at one-per-mille
  precision even though new edits snap to ten per-mille.
- **Verification:** `pnpm test` passed 19 pure tests and 10 component tests; `pnpm lint`, `pnpm
  typecheck` and `pnpm build` passed. `uv run pytest -q` passed 300 tests with the known upstream
  Starlette warning; `uv run ruff check .`; `uv run mypy coordinator/src/e87canbus`; `uv run python
  scripts/generate_custom_protocol.py --check`; `bash -n scripts/*.sh`; and `git diff --check`
  passed. Vite emitted a chunk-size advisory after adding Recharts. Collaborative-browser checks
  passed in light and dark themes at 480x800 without horizontal overflow and at 1280x900. A numeric
  edit remained browser-local before Apply; Apply updated runtime state without saving; and ArrowUp
  changed a focused chart slider. A dirty numeric draft value of 45% survived a backend stop,
  restart and WebSocket reconnection unchanged. Pointer/touch dragging and an actual target
  touchscreen were not exercised.
- **Documentation:** Updated `frontend/README.md` with the three-state workflow, action semantics,
  reconnect/conflict behavior, simulation-only boundary and test command; updated this status and
  entry.
- **Dependencies/migrations:** Added Recharts 3.8 through the shadcn chart CLI and added the shadcn
  Input, Label and Select primitives through the configured CLI. Added Vitest, jsdom and React
  Testing Library as development dependencies for required component interaction tests. Preserved
  pnpm lockfile version 6; no storage migration.
- **Remaining:** Complete browser verification for pointer/touch dragging and chart extremes.
  Exercise the actual target touchscreen before in-car use.
- **Next handoff:** Phase 6 may proceed now and replace only the versioned evaluator and chart line
  type; it must preserve the editor's integer API values and draft/active/saved state separation.
  Actual touchscreen verification remains required before in-car use.

### 2026-07-14 — Phase 4: profile API and publication verified

- **Status:** Verified
- **Scope:** Exposed saved-profile CRUD, authoritative curve state and runtime activation through
  the simulator FastAPI composition. No frontend editor, smooth interpolation, controller transport
  or live deployment authority was added.
- **Changed:** Added strict integer-unit request parsing and complete profile/curve responses;
  consistent typed API errors; optimistic update/delete conflict details; saved-provenance matching;
  SQLite initialization at API lifespan startup; configurable database path; a bounded simulation
  activation command that dispatches the existing kernel input; and WebSocket profile-catalog
  invalidation after committed CRUD. An activation that commits but then encounters an immediate
  runtime-effect failure returns typed `503` while retaining and publishing the authoritative fatal
  snapshot.
- **Decisions:** Save and activation remain separate endpoints and failure domains. Repository work
  uses the adapter's independent short-lived SQLite connections in worker threads, so no database
  transaction is held while activation waits in the runtime queue. False saved provenance is
  rejected with `409`; it is never silently published. Catalog publication is an invalidation-only
  event, while reconnect recovery uses the existing full active snapshot plus a fresh list request.
  Delete carries `expected_revision` as a query parameter. The unauthenticated API remains loopback
  by default and is explicitly not an in-car authorization boundary.
- **Verification:** `uv run pytest -q` (300 passed); `uv run ruff check .`; `uv run mypy
  coordinator/src/e87canbus`; `uv run python scripts/generate_custom_protocol.py --check`; `bash -n
  scripts/*.sh`; and `git diff --check` all passed. A clean-root test run confirmed no default
  SQLite artifact is created by tests. The existing FastAPI test dependency emitted one upstream
  Starlette `httpx` deprecation warning.
- **Documentation:** Updated `coordinator/README.md` with database composition, endpoint semantics,
  error/publication contracts and the loopback security boundary; updated this phase status and
  entry.
- **Dependencies/migrations:** None. The API initializes and uses the existing Phase 2 migration;
  no schema change was required.
- **Remaining:** None for Phase 4. Phase 5 can consume these contracts to keep draft, active and
  saved values visibly distinct.
- **Next handoff:** The frontend should fetch `/api/steering/curve-state` and
  `/api/steering/profiles`, treat `steering_profile_catalog_changed` only as a refetch signal, and
  perform save then activation as two explicit results when offering a combined user action.

### 2026-07-14 — Phase 3: runtime curve activation verified

- **Status:** Verified
- **Scope:** Implemented in-memory hot activation of a validated steering curve through the
  coordinator kernel. No profile API, database startup composition or controller synchronization
  was added.
- **Changed:** Added the immutable active-curve projection and activation statuses in
  `coordinator/src/e87canbus/features/steering.py`; added `ActivateSteeringCurve` as the sole ordered
  runtime input; removed the transitional float curve from `SteeringConfig`; passed the active
  definition explicitly through pure steering calculations; and serialized the complete active
  projection in authoritative simulator snapshots.
- **Decisions:** A newly constructed runtime starts at activation revision 1. Only a changed
  definition increments that revision or emits an immediate Auto command; identical bytes may
  update matching saved provenance through a normal kernel commit without a spurious command.
  Startup composition can pass an already selected active value into the kernel, keeping database
  I/O outside it. The in-process consumer reports `active`; `activating` and `activation_failed` are
  reserved in the snapshot contract without a fake acknowledgement or transport.
- **Verification:** `uv run pytest -q` (279 passed); `uv run ruff check .`; `uv run mypy
  coordinator/src/e87canbus`; `uv run python scripts/generate_custom_protocol.py --check`; `bash -n
  scripts/*.sh`; and `git diff --check` all passed. The existing FastAPI test dependency emitted one
  upstream Starlette `httpx` deprecation warning.
- **Documentation:** Updated `coordinator/README.md` with runtime ownership, startup selection,
  revision, idempotency, immediate output and status behavior; updated this phase status and entry.
- **Dependencies/migrations:** None.
- **Remaining:** None for Phase 3. Configuring and loading a deployment startup profile belongs to
  the later composition that first consumes the repository. HTTP queueing, saved-provenance lookup
  and activation responses belong to Phase 4.
- **Next handoff:** Phase 4 can validate claimed saved provenance with the repository, enqueue one
  `ActivateSteeringCurve`, and return/publish its commit snapshot without mutating runtime state
  directly.

### 2026-07-14 — Phase 2: SQLite profile persistence verified

- **Status:** Verified
- **Scope:** Implemented the coordinator-owned SQLite repository for complete named steering
  profiles, including initialization, migration, seeding, CRUD and optimistic revisions. No API or
  runtime activation behavior was added.
- **Changed:** Added the domain-facing repository protocol and typed failures in
  `coordinator/src/e87canbus/features/profile_repository.py`; added the file-backed adapter in
  `coordinator/src/e87canbus/adapters/sqlite_profiles.py`; factored profile-name validation into a
  reusable domain function; and added real temporary-file tests covering migration, seed, CRUD,
  ordering, conflicts, integrity failures, rollback and reopen behavior.
- **Decisions:** The built-in seed uses stable ID `00000000-0000-4000-8000-000000000001` and the
  name `Built-in default`. Lists sort by case-insensitive name then profile ID. Each operation opens
  its own checked SQLite connection; initialization is an explicit concrete-adapter method rather
  than part of the domain repository protocol. The adapter uses WAL journaling, `FULL` synchronous
  durability and a five-second busy timeout. Live and simulator startup remain unchanged because
  this phase has no storage consumer; a later composition phase must supply the deployment path and
  call initialization.
- **Verification:** `uv run pytest -q` (270 passed); `uv run ruff check .`; `uv run mypy
  coordinator/src/e87canbus`; `uv run python scripts/generate_custom_protocol.py --check`; `bash -n
  scripts/*.sh`; and `git diff --check` all passed. The existing FastAPI test dependency emitted one
  upstream Starlette `httpx` deprecation warning.
- **Documentation:** Updated `coordinator/README.md` with repository ownership, initialization,
  durability, migration, seed, ordering, integrity and composition behavior; updated this phase
  status and entry.
- **Dependencies/migrations:** No dependency added. SQLite migration 1 creates `schema_migrations`
  and `steering_profiles`; initialization refuses a migration version newer than the code supports.
- **Remaining:** None for Phase 2. Supplying the deployment database path and invoking explicit
  initialization belong with the later composition that first consumes the repository.
- **Next handoff:** Phase 3 remains independent of storage. Phase 4 can depend on the
  `SteeringProfileRepository` protocol, translate its typed failures, configure the SQLite path and
  initialize the concrete adapter without importing SQLite into API orchestration.

### 2026-07-14 — Phase 1: profile domain model verified

- **Status:** Verified
- **Scope:** Implemented the versioned immutable curve definition, stored-profile metadata value,
  validation, canonical serialization, fingerprinting, built-in definition and calculation
  projection required by Phase 1.
- **Changed:** Added the fixed eight-point integer-unit domain contract and sole built-in definition
  in `coordinator/src/e87canbus/features/steering.py`. `SteeringConfig` now derives its transitional
  float curve from that definition, with no runtime activation or ownership change. Added focused
  domain tests and updated existing application/simulation expectations for the documented
  half-per-mille quantization tolerance.
- **Decisions:** Profile names are trimmed, non-empty and limited to 100 characters. Profile IDs
  use canonical lowercase hyphenated UUID text. Timestamps use UTC ISO 8601 with six fractional
  digits and `Z`. Definition canonical bytes are compact key-sorted UTF-8 JSON; the fingerprint is
  its lowercase SHA-256 digest. These choices make persisted values deterministic without adding
  persistence or API types.
- **Verification:** `uv run pytest -q` (249 passed); `uv run ruff check .`; `uv run mypy
  coordinator/src/e87canbus`; `uv run python scripts/generate_custom_protocol.py --check`; and
  `git diff --check` all passed. The existing FastAPI test dependency emitted one upstream
  Starlette `httpx` deprecation warning.
- **Documentation:** Documented authoritative units, validation ownership, schema/interpolation
  support, canonical bytes, fingerprint scope and timestamp format in `coordinator/README.md`.
- **Dependencies/migrations:** None. The existing runtime float field remains as a projection for
  compatibility and is scheduled for removal in Phase 3.
- **Remaining:** None for Phase 1. Persistence, runtime activation, API, editor and smooth
  interpolation remain in later phases.
- **Next handoff:** Phase 2 can persist the domain values directly. It must preserve the exact
  integer fields, UUID/name constraints, canonical timestamps and optimistic revision contract;
  it must not fingerprint stored metadata.

### 2026-07-14 — Version-1 fixed speed grid selected

- **Status:** Not started
- **Scope:** Resolved the blocking product input for Phase 1; no implementation code was changed.
- **Changed:** Defined eight fixed points at `0, 10, 20, 30, 60, 100, 160, and 250 km/h` and the
  built-in per-mille values derived from the current curve.
- **Decisions:** Point X positions are immutable in schema version 1. The grid is denser at low
  speeds, retains the current `30` and `100 km/h` breakpoints, and exposes two high-speed controls.
  The `250 km/h` endpoint is an editor-domain choice, not a hardware claim.
- **Verification:** Recalculated the current piecewise-linear values at every selected speed and
  checked the documentation with `git diff --check`.
- **Documentation:** Updated the roadmap and Phase 1 domain-model contract.
- **Dependencies/migrations:** None; changing this grid after profiles exist will require a new
  schema version or explicit migration.
- **Remaining:** All six implementation phases.
- **Next handoff:** Phase 1 can begin by encoding the documented grid, integer values and validation
  without another product decision.

### 2026-07-14 — Roadmap prepared

- **Status:** Not started
- **Scope:** Planning only; no curve implementation code was changed.
- **Changed:** Added phased plans for the profile model, SQLite persistence, runtime activation,
  API, editor and smooth interpolation, plus Proposed ADR 0007.
- **Decisions:** Draft, active and saved state remain distinct. The first editor release uses honest
  linear interpolation. Controller synchronization remains outside these phases.
- **Verification:** Documentation links and `git diff --check` reviewed.
- **Documentation:** This directory and the ADR index.
- **Dependencies/migrations:** None.
- **Remaining:** All six implementation phases.
- **Next handoff:** Superseded by the later grid-selection entry above.
