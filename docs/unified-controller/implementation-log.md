# Unified controller implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, material decisions, verification evidence and unresolved issues. It is not a transcript of
commands, a replacement for commit history or permission to claim hardware behavior from software
simulation.

## How to use this log

- Read the roadmap, current phase document, applicable ADRs and all existing entries before work.
- Append an entry when a phase or meaningful slice is implemented, deliberately deferred or
  blocked.
- Keep entries concise and factual. Link files and tests instead of pasting large code excerpts.
- Add new entries newest first. Do not rewrite history when later work changes direction.
- Record departures from the phase specification and why they were necessary.
- Record dependency, lockfile, generated-contract, SQLite migration and public API consequences.
- Distinguish focused tests, repository-wide checks, browser checks, soak tests and physical/CAN
  evidence.
- State whether real CAN TX was available and enabled. Never imply physical output from simulation.
- Record compatibility paths introduced and the exact later phase responsible for removing them.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Runtime contracts | Verified | 2026-07-15 | Architecture, runtime contracts and regression baseline complete |
| 2 — Unified composition | Verified | 2026-07-15 | One bounded controller/API lifecycle with validated adapter selection |
| 3 — Commands and resources | Verified | 2026-07-15 | Typed commands, development actions and precise durable resources complete |
| 4 — Socket.IO publication | Verified | 2026-07-15 | Fixed topics, reconnect snapshot and bounded delivery complete |
| 5 — Frontend data ownership | Not started | — | Zustand live state and TanStack Query HTTP ownership |
| 6 — Simulation/device convergence | Not started | — | Physical, emulated and observer pathways |
| 7 — Reliability/deployment | Not started | — | Failure policy, health, shutdown and service operation |
| 8 — Cutover/acceptance | Not started | — | Legacy removal, integrated checks and soak evidence |

## Current handoff

Start Phase 5 from the generated protocol-v1 live schema and explicit TypeScript event map. Create
one `socket.io-client` connection outside React, replace complete snapshots on `boot_id` change,
reject older/duplicate topic revisions in Zustand, subscribe to trace only while needed, and move
HTTP resources/mutations exclusively to TanStack Query. Invalidate/refetch the small durable set
once after reconnect because `resources.changed` is not replayed. Remove the frontend's raw `/ws`
and `/api/snapshot` ownership in Phase 5, but leave the backend compatibility reads for Phase 8.
Preserve HTTP-only business commands, separate simulation `session_id`, boot-scoped service and
topic revisions, bounded trace, exact CORS, deny-by-default live output, and the Phase 7
effect/actuator-failure health-commit handoff.

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass. Use `Verified` only when every phase
completion criterion and all relevant repository-wide, browser, soak and adapter checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The exact phase or smaller slice attempted.
- **Changed:** Important files, contracts, migrations and externally visible behavior.
- **Decisions:** Material implementation choices or deviations, with reasons.
- **Verification:** Exact focused and repository-wide checks run and their outcome.
- **Browser/soak/physical checks:** Scenarios, duration and observations, or explicitly not run.
- **Documentation:** README, ADR, API, schema or operator documents updated.
- **Dependencies/migrations:** None, or additions and operational/compatibility impact.
- **Compatibility/removal:** Temporary compatibility retained and its removal owner, or none.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact, risk or prerequisite for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-15 — Phase 4: bounded Socket.IO live-state publication

- **Status:** Verified
- **Scope:** Added the fixed protocol-v1 Socket.IO live-state transport, complete connection/resync
  snapshots, boot/topic revisions, latest-state coalescing, opt-in bounded trace and precise
  resource changes. Frontend ownership remains Phase 5; raw simulated reads remain compatibility.
- **Changed:** Mounted one `python-socketio` server with FastAPI at `/socket.io` under the exact
  same-origin/development-origin policy. Added `controller.snapshot`, `vehicle.state`,
  `engine.state`, `steering.state`, `buttons.state`, `devices.state`, `controller.health`,
  `resources.changed` and `trace.batch`, plus transport-only resync/trace controls. Service
  snapshots now compose immutable application, diagnostics, desired LED and selected-adapter
  observations with a monotonic boot-scoped revision and fixed topic revisions; simulation reset
  retains its distinct reset-local `session_id`. Runtime executions expose actual commit topics and
  counts so exact HTTP command acknowledgements are remapped to their matched service revision.
  The owner hands snapshots to a six-entry latest-topic map, bounded trace/resource rings and one
  loop wakeup without awaiting ASGI or creating per-commit tasks. Telemetry is capped at 25 Hz;
  trace is opt-in at 10 Hz with at most 100 rows per batch. Each Engine.IO peer has a finite
  64-packet outbound queue; saturation aborts that peer and increments a bounded transport counter
  instead of blocking an emitter or evicting arbitrary Socket.IO control/data packets. Publisher
  flushing and Socket.IO teardown share one two-second shutdown deadline, after which remaining
  tasks are cancelled and awaited. Pydantic models generate
  `protocol/live-events-v1.schema.json`; an explicit checked TypeScript map defines client events
  and stale/duplicate/new-boot handling without introducing frontend socket ownership yet.
- **Decisions:** Used a thread-safe latest-topic map and one async publisher rather than an event
  queue. The service owns monotonic publication identity across simulation resets while legacy
  compatibility snapshots keep their reset-local revision. Adapter-only device observation changes
  receive a service revision without mutating controller state. Transport failures increment
  publisher diagnostics only; Phase 7 still owns controller-health reconciliation. Socket.IO
  recovery is always a complete snapshot and does not depend on durable replay. Slow peers are
  disconnected on queue saturation because silently dropping an oldest queued packet could discard
  a control packet or complete snapshot. The raw `/ws` mirror keeps bounded, ordered whole execution
  batches from the same publisher to avoid mixing snapshots and trace across simulation sessions.
- **Verification:** Full `uv run pytest -q`: 503 passed with one existing Starlette/httpx
  deprecation warning. `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus`, `uv run
  python scripts/generate_custom_protocol.py --check`, `uv run python
  scripts/generate_live_contract.py --check`, `bash -n scripts/*.sh` and `git diff --check` passed.
  `pnpm test`: 46 unit and 55 component tests passed. `pnpm lint`, `pnpm typecheck` and `pnpm build`
  passed; Vite 8.1.4 transformed 2,936 modules.
- **Browser/soak/physical checks:** A bounded 500-input synthetic burst processed at 6,914.2/s in
  0.072315 s. Across the 0.422953 s observation it emitted two `vehicle.state` and two
  `trace.batch` events, retained at most six fixed topics and 298 of 2,000 trace rows, bounded each
  trace batch to 100, reached controller inbox depth 426 and maximum measured command completion
  latency 0.059263 s, and recorded zero publication failures with healthy controller diagnostics.
  A real Uvicorn plus Socket.IO websocket client received a complete protocol-v1 snapshot over the
  websocket transport; automated polling composition tests cover the same payload. No browser
  visual or physical check was required. An installed-Engine.IO integration test proves the stock
  queue is unbounded, the composed queue is finite, and a third undrained packet at capacity two
  aborts only that peer while retaining a saturation diagnostic. A stalled-emitter/stalled-socket
  teardown test proves one 50 ms test deadline and no remaining named publisher tasks. Real CAN TX
  was unavailable and not enabled; no physical CAN or steering evidence was claimed.
- **Documentation:** Updated coordinator, simulation, root and protocol guidance; generated and
  checked the protocol-v1 JSON schema; updated this status/handoff record.
- **Dependencies/migrations:** Added `python-socketio` 5.16.3 and locked `python-engineio`, `bidict`,
  `simple-websocket` and `wsproto`. No SQLite or generated CAN protocol migration changed.
- **Compatibility/removal:** Retained simulated `GET /api/snapshot` and raw `/ws` as bounded reads
  from the canonical service/publisher; Phase 5 removes their frontend consumers and Phase 8 removes
  the backend endpoint/adapter. No Socket.IO business-command or alternate state-owner facade was
  added.
- **Remaining:** None for Phase 4. Phase 5 owns frontend Socket.IO/Zustand and TanStack Query data
  ownership; Phase 7 still owns effect/actuator-failure health commits.
- **Next handoff:** Use `frontend/src/api/live-events.ts` and the generated schema as the Phase 5
  boundary. A changed `boot_id` replaces the whole live store; matching boots compare each topic's
  revision independently. Resource events are hints and reconnect performs one bounded refetch.

### 2026-07-15 — Phase 3: typed commands and precise durable resources

- **Status:** Verified
- **Scope:** Replaced simulator-owned HTTP mutations with typed semantic commands and explicit
  development-adapter actions, made settings/profile invalidation precise, and prepared frontend
  HTTP/query ownership. Socket.IO, Zustand live state and physical output remain later phases.
- **Changed:** Added idempotent `SetMaximumAssistance` and `SetSteeringMode` controller inputs plus
  the existing typed curve activation path to both live and simulated adapters. Added
  `PUT /api/commands/maximum-assistance`, `PUT /api/commands/steering-mode`,
  `POST /api/commands/activate-steering-profile` and the current draft-editor extension
  `PUT /api/commands/steering-curve`. Commands submit exactly once through the bounded service,
  wait with a finite configured timeout and return only `accepted`, `boot_id` and their matched
  commit revision. Replaced every simulator mutation URL with `/api/dev/simulation/*`, registered
  explicit unavailable-adapter failures in live mode, and removed the old reset/button/vehicle,
  curve-activation and simulated `ActivateCurve` paths rather than retaining aliases. Settings and
  profile CRUD continue to return complete revisioned SQLite resources; successful mutations now
  emit typed `resources.changed` values with exact resource, ID and revision. The frontend now
  sends all HTTP through the shared API client, uses domain-specific query keys/options, replaces
  initiating mutation caches precisely, handles exact resource invalidation and consumes small
  command acknowledgements. Removed the final `KernelInput` compatibility alias and migrated its
  remaining tests. Generic steering reads now serialize only the canonical service
  `ApplicationSnapshot` and have no simulator compatibility-type dependency.
- **Decisions:** Kept saved-profile activation distinct from unsaved draft activation so the server
  resolves and verifies saved identity/revision without accepting client-claimed provenance.
  `ControllerCommandResult` carries the matched revision and failure state from the owner, avoiding
  a later snapshot race. Steering mode remains an independent desired value beneath temporary
  maximum assistance. Current settings are display configuration and profile rows are inert until
  an explicit activation command, so resource CRUD has no runtime configuration to reconcile at
  startup. Development routes remain callable in live composition only to return the stable
  `simulation_adapter_unavailable` problem; they cannot reach an absent adapter.
- **Verification:** Full `uv run pytest -q`: 482 passed with one existing Starlette/httpx
  deprecation warning. `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus`, `uv run
  python scripts/generate_custom_protocol.py --check`, `bash -n scripts/*.sh` and `git diff
  --check`: passed. `pnpm test`: 45 unit and 55 component tests passed. `pnpm lint`, `pnpm
  typecheck` and `pnpm build`: passed; Vite 8.1.4 transformed 2,936 modules.
- **Browser/soak/physical checks:** No browser or soak run was required for this transport/resource
  phase. FastAPI/WebSocket tests covered exact command bodies, strict validation, bounded overload,
  timeout ambiguity, exact typed HTTP submissions, repeat-safe command topics/effects, accepted
  live-mode semantic commands, unavailable live simulation capability, revision conflicts,
  precise invalidations and virtual-CAN button traversal. Real CAN TX was unavailable and not
  enabled; no physical CAN or steering evidence was claimed.
- **Documentation:** Updated coordinator, frontend, simulator and prior feature API guidance for
  the command/development namespaces and `resources.changed`; updated this status/handoff record.
- **Dependencies/migrations:** None. No dependency, lockfile, generated protocol or SQLite schema
  changed. Added the positive `runtime_command_timeout_s` configuration value; existing SQLite v2
  settings/profile data remains valid without migration.
- **Compatibility/removal:** Removed all superseded HTTP mutation endpoints, the simulated
  activation wrapper and the internal `KernelInput` alias in this phase. The raw simulated
  `GET /api/snapshot`, `/ws` snapshot/trace stream and compatibility snapshot responses from
  development actions remain only for current live-state consumers; Phase 5 migrates their
  frontend ownership and Phase 8 removes them.
- **Remaining:** None for Phase 3. Phase 4 must transport live topics and `resources.changed` over
  bounded Socket.IO without turning socket client events into business commands.
- **Next handoff:** Build Phase 4 publication from service commits and exact resource changes. Treat
  command acknowledgements as processing receipts, not authoritative state, and preserve their
  matched boot/revision semantics.

### 2026-07-15 — Phase 2: unified controller and API composition

- **Status:** Verified
- **Scope:** Replaced the separate live runner and asynchronous simulator-API owner with one
  bounded `ControllerService` lifecycle selected for live or simulated adapters. Socket.IO,
  frontend state ownership, semantic-command redesign and physical output remain later phases.
- **Changed:** Added the composition-owned controller service with a dedicated owner thread, one
  bounded inbox, one timer schedule, thread-safe acknowledgements, immutable cached service
  snapshots and a fresh opaque `boot_id`. Added validated live/simulated CAN, device-authority,
  steering-capability and TX-grant selections. Converted the SocketCAN path into a live runtime
  adapter and renamed the simulator state holder to a lazy-started simulated runtime adapter owned
  only by the service in `simulation/runtime.py`. FastAPI now initializes SQLite, starts one service,
  publishes readiness after startup effect synchronization, submits every retained simulator action
  through the service and requests safe shutdown. Added `e87canbus run --mode live|simulated`;
  live mode exposes an RX-only API and does not register development simulator
  mutation/raw-WebSocket routes. Removed the
  separate simulation command-queue configuration and all `SimulationEngine`, `run_live` and
  `create_app(engine=...)` construction paths. Removed the independently executable legacy live
  owner loop and the obsolete `e87canbus-sim-api` console entry/modules rather than retaining
  runtime or CLI facades.
- **Decisions:** Kept blocking CAN receive/effect I/O off the ASGI loop and synchronously bridged
  bounded legacy WebSocket publication back to that loop so command/effect/publication order is
  retained. Service snapshots cache the complete application projection and diagnostics
  atomically; simulation reset changes only `session_id`, not service `boot_id`. Live construction
  is side-effect-free until lifespan startup and always uses the production router. Physical
  steering selection fails validation because no evidence-backed adapter/grant exists. Phase 7's
  effect-failure health-commit gap was not duplicated or changed. The service carries its immutable
  composition mode and FastAPI rejects mismatched service injection. Live shutdown commits the
  safe transition before closing adapters, then verifies every reader exited and surfaces failure.
- **Verification:** Full `uv run pytest -q`: 471 passed with one existing Starlette/httpx
  deprecation warning. `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus`, `uv run
  python scripts/generate_custom_protocol.py --check`, `bash -n scripts/*.sh` and `git diff
  --check`: passed. `pnpm test`: 45 unit and 53 component tests passed. `pnpm lint`, `pnpm
  typecheck` and `pnpm build`: passed; Vite 8.1.4 transformed 2,936 modules.
- **Browser/soak/physical checks:** No browser or soak check was required because retained frontend
  transport behavior is covered by the unchanged component/API suites. Simulated adapter and fake
  disabled/listen-only SocketCAN lifecycle, overflow, cleanup, stuck-reader detection, composition
  mismatch and TX-grant scenarios passed. A repository search confirmed no second live owner loop,
  old simulator engine module/name or legacy simulator console entry remains outside historical
  specification/log text. Real CAN TX was unavailable and not enabled; no physical CAN or steering
  evidence was claimed.
- **Documentation:** Updated root/coordinator operation guidance, setup and simulation docs with
  the canonical mode-selecting entry point, adapter behavior, development-route availability and
  default RX-only live boundary. Updated this status/handoff record.
- **Dependencies/migrations:** No dependency, lockfile, generated protocol or SQLite schema changed.
  The obsolete `e87canbus-sim-api` project script and simulation-only command queue setting were
  removed; the unified `e87canbus run --mode simulated` command and existing
  `runtime_inbox_capacity` replace them.
- **Compatibility/removal:** Current simulator HTTP payloads and raw `/ws` events remain direct
  transports over `ControllerService`; Phase 8 owns their removal after frontend migration. No
  legacy runtime, construction or CLI facade remains.
- **Remaining:** None for Phase 2. Phase 3 must add typed semantic live commands and precise durable
  resources; Phase 4 replaces raw WebSocket publication; Phase 7 reconciles failure-only health
  publication and final operational failure policy.
- **Next handoff:** Build Phase 3 routes only against `ControllerService.submit` and repositories.
  Do not reintroduce a simulator owner, accept ambiguous toggles or grant live TX/physical steering.

### 2026-07-15 — Phase 1: runtime contracts and regression baseline

- **Status:** Verified
- **Scope:** Accepted the unified-controller architecture, consolidated framework-independent
  runtime vocabulary and added focused characterization of commit topic semantics. Public
  transports and process composition were not changed.
- **Changed:** Added accepted ADR 0008 and its decision-index entry. Renamed the primary closed
  runtime union to `ControllerInput`, retained `KernelInput` as a compatibility alias, made profile
  activation carry an explicit monotonic decision timestamp, added the closed `StateTopic` enum and
  immutable `Commit.changed_topics`, and migrated live/simulation annotations to the new name.
  Startup marks the complete set of currently kernel-owned projections; later commits derive
  vehicle, engine, steering, button and health hints from fixed projection differences. Added
  focused assertions for startup, no-change, steering/button, vehicle, health and
  profile-activation topics. Reconciled stale
  frontend regression tests with the accepted drive redesign: retained its visual layout and 32px
  trace rows, restored screen-reader-only Drive/speed/RPM/stage/unavailable semantics that the
  redesign had accidentally removed, and updated only the stale 33px trace expectation.
- **Decisions:** Kept the current application snapshot shape and all HTTP/raw-WebSocket payloads
  unchanged. Recorded the version 1 future live envelope, opaque per-service `boot_id`, boot-scoped
  revisions, topic-local consumer revisions, distinct simulation session/trace identity and
  monotonic-versus-UTC time ownership in ADR 0008. Did not make current CAN-effect or actuator
  failures return commits: they currently update diagnostics without a revision, and Phase 7 owns
  reconciliation with health-topic publication while preserving non-recursive failure feedback.
  Kept `ApplicationSnapshot` as the complete application projection without duplicating derived
  button LEDs, adapter-owned observed devices or runtime diagnostics. Kernel startup marks only
  its current projections, not `devices`; a focused assertion ties the button topic to the one
  complete immutable 16-LED effect, while existing tests retain device and health ownership.
- **Verification:** Focused runtime/live/simulation/API/settings/profile suite: 180 passed. Full
  `uv run pytest -q`: 472 passed with one existing Starlette/httpx deprecation warning. `uv run
  ruff check .`, `uv run mypy coordinator/src/e87canbus` and `uv run python
  scripts/generate_custom_protocol.py --check`: passed. `pnpm test`: 45 unit and 53 component tests
  passed. `pnpm lint`, `pnpm typecheck` and `pnpm build`: passed; Vite 8.1.4 transformed 2,936
  modules. `git diff --check`: passed. Existing Node experimental-module, missing local Fig shell
  hook and Starlette/httpx deprecation notices were non-failing.
- **Browser/soak/physical checks:** Not run; Phase 1 changes no public behavior and requires no
  browser, soak, physical CAN or hardware evidence. Real CAN TX was unavailable and not enabled.
- **Documentation:** Added `docs/decisions/0008-unified-controller-architecture.md`, indexed it in
  `docs/decisions/README.md`, clarified projection ownership there, and updated this status/handoff
  record.
- **Dependencies/migrations:** None. No package, lockfile, generated protocol or SQLite migration
  changed. The backend test run applied the existing settings migration to the tracked development
  database; that incidental file change was restored exactly and is not part of this phase.
- **Compatibility/removal:** Existing HTTP and raw-WebSocket simulator contracts remain unchanged
  and Phase 8 owns their removal after frontend migration. `KernelInput` remains an internal alias
  for current imports; Phase 8 owns removal after internal consumers migrate.
- **Remaining:** None for Phase 1. Phase 7 must close the documented effect/actuator-failure health
  commit gap.
- **Next handoff:** Phase 2 can build one lifecycle against `ControllerInput`, `Commit` and the
  closed topic vocabulary. It must create a fresh opaque service `boot_id` per start, preserve the
  separate simulation reset session identity, keep default live output deny-by-default and avoid
  targeting the temporary raw-WebSocket shape.

### 2026-07-15 — Roadmap specification prepared

- **Status:** Not started
- **Scope:** Converted the approved unified controller, Socket.IO, Zustand/TanStack Query and
  production-path simulation architecture into assignable phase specifications. No application
  implementation was performed.
- **Changed:** Added the roadmap README, eight phase documents, this implementation log and the
  reusable phase-agent prompt under `docs/unified-controller/`.
- **Decisions:** Kept one modular process and one state owner; separated backend composition,
  commands, publication, frontend ownership, simulation convergence, reliability and cutover so
  each agent receives a bounded outcome. Compatibility removal is explicit rather than mixed into
  early migrations. Full-car simulation and unsupported physical behavior remain non-goals.
- **Verification:** Checked phase dependencies, ownership rules, compatibility handoffs, public
  contract direction and completion criteria against the approved architecture and existing ADRs.
  No application tests were required for documentation-only work.
- **Browser/soak/physical checks:** Not applicable; no executable behavior changed.
- **Documentation:** All files in this directory are new specification documents.
- **Dependencies/migrations:** None. Future phases propose Socket.IO dependencies and may change
  public contracts, but this specification applies neither.
- **Compatibility/removal:** The documents permit temporary existing HTTP/raw-WebSocket behavior;
  Phase 8 owns its final removal after Phase 5 moves the frontend.
- **Remaining:** Implement Phases 1-8 in order and record actual results here.
- **Next handoff:** Start with Phase 1. Inspect current code and tests rather than treating proposed
  file names as current truth, and preserve the deny-by-default live output boundary.
