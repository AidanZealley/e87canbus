# Car frontend implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, material decisions, verification evidence and unresolved issues. It is not a transcript of
commands, a replacement for commit history or permission to claim hardware behavior from software
simulation.

## How to use this log

- Read the roadmap, current phase document, relevant ADRs and all existing entries before starting.
- Append an entry when a phase or meaningful slice is implemented, deliberately deferred or
  blocked.
- Keep entries concise and factual. Link files and tests rather than pasting large code excerpts.
- Do not rewrite earlier entries when a later implementation changes direction; add a correcting
  entry.
- Record departures from the phase specification and why they were necessary.
- Record dependency, generated-route, SQLite migration and public API consequences explicitly.
- Distinguish focused automated tests, repository-wide checks, browser visual checks and physical
  display testing.
- Never claim verified BMW messages, real device health or physical steering safety from this work.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Routing and layouts | Verified | 2026-07-14 | TanStack Router, chooser, `/dev` and `/car` shell |
| 2 — Application settings | Verified | 2026-07-14 | Revisioned SQLite settings, API and query boundary |
| 3 — Engine telemetry simulation | Verified | 2026-07-14 | Independent synthetic RPM/oil/coolant CAN path |
| 4 — Device health | Verified | 2026-07-14 | Explicit simulator status projection and controls |
| 5 — Car UI foundation | Verified | 2026-07-14 | Long-lived car data owner, warnings and reusable instruments |
| 6 — Car screens | Not started | — | Overview, drive, steering and settings views |
| 7 — Verification and acceptance | Not started | — | Integrated checks and 800x480 browser matrix |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass. Use `Verified` only after every phase
completion criterion and all relevant repository-wide and visual checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The exact phase or smaller slice attempted.
- **Changed:** Important files, contracts, migrations and externally visible behavior.
- **Decisions:** Material implementation choices or deviations, with reasons.
- **Verification:** Exact tests/checks/browser scenarios run and their outcome.
- **Visual/physical checks:** Viewports/themes/states inspected, or explicitly not run.
- **Documentation:** README, API, schema or roadmap documents updated.
- **Dependencies/migrations:** None, or additions and operational/compatibility impact.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact, risk or prerequisite for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-14 — Phase 5: shared car data and instrument foundation

- **Status:** Verified
- **Scope:** Implemented the complete Phase 5 `/car` data/settings owner, canonical presentation
  utilities, persistent temperature warnings, RPM stages, compact shared faults and reusable
  instruments; final Phase 6 screen composition remains out of scope.
- **Changed:** Moved the car shell into its component boundary and wrapped every child route in one
  snapshot/query/WebSocket and settings context. The context exposes masked application telemetry,
  steering-controller state, devices, connection state, authoritative-or-default settings with a
  distinct fault/error, and persistent oil/coolant severity. Added telemetry value, temperature
  gauge, segmented RPM bar and stable-order device footer components.
- **Decisions:** Reused the existing simulator query key, cache merge and WebSocket implementation
  rather than adding a parallel store. Connection loss masks live speed/engine presentation and
  device health; settings and navigation remain usable. Temperature severity is derived from the
  current render inputs before its result is persisted for later hysteresis, so promotions,
  invalidation and threshold changes cannot paint an old severity. A settings threshold change
  derives severity afresh from the current valid canonical reading, while ordinary readings use
  fixed three-degree Celsius demotion hysteresis. Real offline devices use destructive styling;
  unavailable placeholders remain muted. Instruments receive formatted/presentation data and do
  not read API state. No later-phase prerequisite was needed.
- **Verification:** Focused Phase 5 checks passed 7 pure utility tests and 12 provider/instrument
  component tests, including first-render severity transitions, fail-closed disconnected devices
  and destructive-offline versus muted-unavailable presentation. `pnpm test` passed 40 unit and 46
  component tests; `pnpm typecheck`; `pnpm lint`;
  `pnpm build`; `uv run pytest -q` (470 passed); `uv run mypy`; `uv run ruff check coordinator`;
  `uv run python scripts/generate_custom_protocol.py --check`; and `git diff --check` passed. The
  existing FastAPI TestClient deprecation and Vite development chunk-size warnings remain
  non-failing.
- **Visual/physical checks:** The live `/car` shell and a temporary browser-only composition of all
  foundation instruments were inspected in light and dark with valid, warning, critical,
  above-redline, stale, unavailable, online and degraded states. At the preview's configured
  800x480 setting (effective 960x576 CSS viewport), the shell and instrument composition had no
  horizontal or vertical document overflow. Stopping the backend showed the compact live-data
  banner while child navigation stayed usable; restarting removed it after reconnect. The preview
  resize operation timed out after applying, as confirmed by measured viewport state. No physical
  display or touch-density validation was run.
- **Documentation:** Updated the frontend README with car data ownership, failure masking,
  hysteresis and reusable instrument behavior, plus this phase log.
- **Dependencies/migrations:** None. There are no backend, HTTP/WebSocket, SQLite, generated route,
  protocol or dependency changes; the new context and components are frontend-internal contracts.
- **Remaining:** None for Phase 5. Final overview, drive, steering and settings compositions and
  target-display touch tuning remain assigned to Phases 6 and 7.
- **Next handoff:** Phase 6 should consume `useCarData` once per screen and project canonical values
  with the pure helpers into the reusable instruments; do not create another snapshot socket or
  reset warning state in child routes.

### 2026-07-14 — Phase 4: explicit simulated device health

- **Status:** Verified
- **Scope:** Implemented the complete Phase 4 device-health projection, queued simulator command,
  HTTP resource and `/dev` controls for the button pad and steering controller; later car footer
  presentation remains out of scope.
- **Changed:** Added closed device ID/status/reason values, a complete stable-order top-level
  `devices` snapshot array, session-owned deterministic defaults and updates, strict
  `PUT /api/simulation/devices/{device_id}/status`, typed frontend snapshot/API boundaries,
  fail-closed unavailable placeholders and two compact shadcn Select controls.
- **Decisions:** Device states remain an explicit presentation-only simulation tuple beside the
  kernel projection. Status commands use the existing bounded owner and publish the normal
  authoritative snapshot without inventing a separate revision source; as with existing
  non-kernel commands, the revision remains kernel-owned. Offline and degraded do not change CAN,
  steering, watchdog or fatal behavior. No later-phase prerequisite was needed.
- **Verification:** Focused simulator engine/API verification passed 92 tests after implementation.
  `uv run pytest -q` (470 passed); `uv run mypy`; `uv run ruff check coordinator`;
  `uv run python scripts/generate_custom_protocol.py --check`; `pnpm lint`; `pnpm test` (33 unit
  and 34 component tests); `pnpm typecheck`; `pnpm build`; and `git diff --check` passed. The
  existing FastAPI TestClient deprecation and Vite development chunk-size warnings remain
  non-failing.
- **Visual/physical checks:** The live `/dev` workbench showed both initial online selectors,
  button-pad degraded and steering-controller offline states with their simulation reasons, no CAN
  frame from either status change, and reset convergence to both online. Light-theme checks at the
  preview's effective 960x576 and 450x800 CSS viewports found no horizontal document overflow; the
  resize operation timed out after applying, but measured layout state and the subsequent snapshot
  confirmed the narrow viewport. No physical device, CAN or display validation was run.
- **Documentation:** Updated coordinator and frontend READMEs with the snapshot, queue, reset,
  fail-closed and presentation-only behavior, plus this phase log.
- **Dependencies/migrations:** None. The public simulator snapshot and initial/reconnect WebSocket
  snapshot now always include `devices`; one PUT endpoint was added. There are no dependency,
  SQLite, generated-protocol or production-CAN changes.
- **Remaining:** None for Phase 4. The minimal car overview footer belongs to Phase 6.
- **Next handoff:** Phase 5 can consume the committed complete device array and must continue to
  treat a missing entry as unavailable/offline; do not infer health from topology or watchdog data.

### 2026-07-14 — Phase 3: independent simulated engine telemetry

- **Status:** Verified
- **Scope:** Implemented the complete Phase 3 RPM, oil-temperature and coolant-temperature path
  from simulated vehicle controls through synthetic CAN, the ordered kernel and HTTP/WebSocket
  snapshots; later car instruments and warning policy remain out of scope.
- **Changed:** Added immutable per-signal observations and explicit valid/never-observed/stale
  projections, a separate one-second engine timeout config, three adjacent simulation-only
  extended PT-CAN codecs, independent vehicle set/emit/silence commands, six vehicle API endpoints,
  strict engine request fields, complete snapshot/frontend types and responsive controls in the
  existing simulated-vehicle card.
- **Decisions:** Temperature selection is stored at the wire's canonical tenth-degree resolution;
  silence removes only simulator emission while the kernel retains history and projects stale
  values as `null`. The live `ProtocolRouter` still declines every synthetic identifier, which is
  named and documented as simulation-only rather than added to the generated provisional custom
  protocol or represented as a BMW candidate. Engine request validation rejects booleans and
  numeric strings before dispatch while accepting ordinary JSON integer temperatures; this
  strictness is scoped to the new models so existing step/speed request compatibility is retained.
  No later-phase prerequisite was needed.
- **Verification:** Focused application/protocol/simulation/API/runtime/architecture tests passed
  153 cases during implementation; targeted simulator API verification passed 43 cases after the
  strict-request regression was added. `uv run pytest -q` (449 passed); `uv run mypy`;
  `uv run ruff check coordinator`; `uv run python scripts/generate_custom_protocol.py --check`;
  `pnpm lint`; `pnpm test` (32 unit and 31 component tests); `pnpm typecheck`; `pnpm build`; and
  `git diff --check` passed. The existing FastAPI TestClient deprecation and Vite development
  chunk-size warnings remain non-failing.
- **Visual/physical checks:** The live `/dev` workbench in the in-app preview showed connected
  never-observed defaults, successful RPM 4200/oil 113 C/coolant 98 C controls, all three extended
  PT-CAN trace IDs, and oil alone becoming stale after silence while RPM/coolant remained valid.
  Light-theme checks at 800x480 and 375x667 preview settings found no horizontal document overflow.
  The host measured effective CSS viewports of 960x576 and 450x800, so target-display physical
  tuning remains the roadmap's later manual work. No physical CAN or display validation was run.
- **Documentation:** Updated coordinator and frontend READMEs with timeout, simulation-only routing,
  null/stale projection and workbench-control behavior, plus this phase log.
- **Dependencies/migrations:** None. The public simulator snapshot and initial/reconnect WebSocket
  snapshot now always include `application.engine`; six POST endpoints were added. There are no
  SQLite migrations, generated-protocol changes or production CAN decoders.
- **Remaining:** None for Phase 3. Car-display instruments, unit presentation and warnings belong to
  Phases 5 and 6.
- **Next handoff:** Phase 4 shares simulator snapshot/API composition; preserve the complete engine
  shape and continue submitting all runtime mutations through the existing bounded owner.

### 2026-07-14 — Phase 2: revisioned application settings

- **Status:** Verified
- **Scope:** Implemented the complete Phase 2 domain, shared SQLite migration, FastAPI resource,
  WebSocket invalidation and frontend settings data boundary; the Phase 6 settings screen remains
  out of scope.
- **Changed:** Added the immutable settings/default contract and validation, repository protocol and
  typed failures, shared database owner with migration 2 and singleton seed, atomic conditional
  updates, exact `GET/PUT /api/settings` serialization, post-commit
  `application_settings_changed` publication, shared frontend API error parsing, stable query
  options, committed-response cache replacement and effective default/fault projection.
- **Decisions:** Used a separate immutable complete-edit candidate so revision and timestamp remain
  repository-owned. The compiled/backend fallback seed uses the canonical Unix-epoch timestamp so
  both sides have one deterministic complete default; fallback use is always identified separately
  from authoritative data. Kept `E87CANBUS_PROFILE_DATABASE` and `--profile-database` compatible
  while making the selected file the shared application database. No later-phase unit conversion or
  settings form was introduced.
- **Verification:** `uv run pytest -q` (392 passed); `uv run mypy`; `uv run ruff check coordinator`;
  `uv run python scripts/generate_custom_protocol.py --check`; `pnpm lint`; `pnpm test` (32 unit and
  28 component tests); `pnpm typecheck`; `pnpm build`; and `git diff --check` passed. Focused Python
  settings/profile/API verification passed 106 tests before the full suite. The existing FastAPI
  TestClient deprecation and Vite development-workbench chunk-size warnings remain non-failing.
- **Visual/physical checks:** Not applicable: this phase adds no user-facing screen or physical
  behavior. The `/car/settings` placeholder is intentionally unchanged for Phase 6.
- **Documentation:** Updated coordinator and frontend READMEs with shared migration ownership,
  settings API semantics, fallback/fault behavior and cache convergence, plus this phase log.
- **Dependencies/migrations:** No dependency changes. SQLite supported version is now 2; fresh files
  apply migrations 1 and 2, version-1 files upgrade in place without profile rewrites, and future
  versions fail closed. The existing database selector now addresses the shared application file.
- **Remaining:** None for Phase 2. Fahrenheit edit conversion belongs to Phase 5 presentation
  utilities and the settings form belongs to Phase 6.
- **Next handoff:** Later car consumers should use `useEffectiveApplicationSettings`; only enable a
  save action when `canSave` is true, keep drafts local and send the complete editable document with
  the loaded revision.

### 2026-07-14 — Phase 1: routed workbench and car shell

- **Status:** Verified
- **Scope:** Implemented the complete Phase 1 routing and layout foundation: the mode chooser,
  preserved development workbench, shared theme control, car route shell and route-aware recovery.
- **Changed:** Added the generated TanStack file route tree, typed router composition, `/`, `/dev`,
  `/car`, `/car/drive`, `/car/steering` and `/car/settings` routes, the isolated icon-only car rail,
  explicit later-phase placeholders, and focused route tests. The simulator toolbar now provides a
  chooser link and shared theme menu. Removed the superseded `App.tsx` composition.
- **Decisions:** Configured root not-found handling so unknown `/car/*` locations cannot inherit or
  expose development navigation. Disabled the Fast Refresh export rule only for route files because
  TanStack automatic code splitting requires route components to stay unexported beside the
  generated `Route` export. No telemetry, settings data or steering behavior was invented.
- **Verification:** `pnpm lint`; `pnpm test` (27 unit and 28 component tests, including 9 new route
  cases); `pnpm typecheck`; `pnpm build`; frozen offline `pnpm install`; `git diff --check`;
  `uv run python scripts/generate_custom_protocol.py --check`; `uv run pytest -q` (330 passed);
  `uv run mypy`; and `uv run ruff check coordinator` all passed. Production build generated
  code-split route chunks; Vite retained its existing large development-workbench chunk warning.
- **Visual/physical checks:** In-app browser checks covered direct loads of `/`, `/dev` and every
  declared car route, both not-found policies, active/accessibly named car navigation, keyboard
  focus, theme menu selection and persistence, light and dark presentation, narrow vertical chooser
  stacking, and document overflow. No horizontal overflow was observed. The preview was configured
  at 800x480 and 375x667; its host reported 1.2x effective CSS dimensions (960x576 and 450x800), so
  native target-display and physical touch-density tuning remain manual follow-up.
- **Documentation:** Updated `frontend/README.md` with the routed entry points, router ownership and
  generated-file rule, plus this phase log.
- **Dependencies/migrations:** Added runtime `@tanstack/react-router`, development
  `@tanstack/router-plugin`, and the shadcn Base UI dropdown-menu source. The pnpm lockfile changed;
  there are no database migrations or backend/API contract changes.
- **Remaining:** None for the Phase 1 route/layout contract. Final screen content and physical
  display tuning remain assigned to later roadmap phases.
- **Next handoff:** Phase 2 can place its future car settings UI under the committed
  `/car/settings` boundary; shared Query and Theme providers already remain above the router.

### 2026-07-14 — Roadmap specification prepared

- **Status:** Not started
- **Scope:** Converted the approved routed development and car-display plan into assignable phase
  specifications. No application implementation was performed.
- **Changed:** Added the roadmap README, seven phase documents, this durable log and the reusable
  stage-agent prompt under `docs/car-frontend/`.
- **Decisions:** Kept the approved 800x480 target while deliberately omitting a fixed control-size
  rule. Physical touch-control density will be tuned manually after an initial implementation.
  Separated routing, persistence, telemetry, device health, shared UI, screens and integrated
  verification so implementation agents can receive bounded scopes.
- **Verification:** Checked document links, phase sequencing, public contract consistency and
  documentation-only worktree scope. No application tests were required for specification work.
- **Visual/physical checks:** Not applicable; no UI was implemented.
- **Documentation:** All files in this directory are new specification documents.
- **Dependencies/migrations:** None. The documents specify future TanStack Router dependencies and
  a future SQLite migration but do not apply either.
- **Remaining:** Implement Phases 1-7 one bounded phase at a time and record actual results here.
- **Next handoff:** Start with Phase 1, or implement independent backend Phases 2-4 with explicit
  coordination around shared FastAPI composition and snapshot files. Read the current repository
  before treating any suggested file boundary as current truth.
