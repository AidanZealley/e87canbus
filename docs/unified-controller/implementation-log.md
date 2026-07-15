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
| 3 — Commands and resources | Not started | — | Semantic commands and precise durable resources |
| 4 — Socket.IO publication | Not started | — | Fixed topics, reconnect snapshot and bounded delivery |
| 5 — Frontend data ownership | Not started | — | Zustand live state and TanStack Query HTTP ownership |
| 6 — Simulation/device convergence | Not started | — | Physical, emulated and observer pathways |
| 7 — Reliability/deployment | Not started | — | Failure policy, health, shutdown and service operation |
| 8 — Cutover/acceptance | Not started | — | Legacy removal, integrated checks and soak evidence |

## Current handoff

Start Phase 3 through `ControllerService.submit`: define typed, idempotent semantic commands and
precise durable-resource boundaries without exposing a kernel or runtime adapter to routes. Live
mode currently registers health/settings only; Phase 3 owns making its command/resource surface
precise. Preserve the fresh service `boot_id`, separate simulation `session_id`, synchronous ordered
effect execution, deny-by-default live output and Phase-8-owned raw simulator transport. Phase 7
still owns the recorded effect/actuator-failure health commit gap.

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
