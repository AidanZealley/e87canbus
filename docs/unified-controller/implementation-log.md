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
| 5 — Frontend data ownership | Verified | 2026-07-15 | One bounded Socket.IO/Zustand path and Query ownership pass browser acceptance |
| 6 — Simulation/device convergence | Verified | 2026-07-15 | Physical, emulated, observer and disabled pathways converge honestly |
| 7 — Reliability/deployment | Verified | 2026-07-15 | Bounded health/failure policy, deterministic shutdown, soak and Pi service verified |
| 8 — Cutover/acceptance | Verified | 2026-07-15 | Legacy removed; integrated, browser and bounded-retention acceptance passed |

## Current handoff

All eight unified-controller phases are verified. One canonical controller/application architecture
remains, with HTTP command/resource ownership, Socket.IO/Zustand live ownership, bounded diagnostics
and deny-by-default physical output. Preserve the service-owned failure policy, exact readiness
semantics, loopback production trust boundary, fixed shutdown order and no-facade cutover. Real CAN
TX, physical steering and optional read-only hardware checks remain under the existing
`docs/requires-hardware` evidence boundaries and are not authorized by this roadmap. Proceed to the
final repository review and completed-work report; do not reopen retired transports or infer
physical behavior from simulation.

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

### 2026-07-15 — Phase 8: legacy ownership removed and integrated cutover verified

- **Status:** Verified
- **Scope:** Removed every remaining legacy live-read and simulator response-snapshot path, reduced
  the runtime/publication seam to the canonical controller service, and exercised integrated
  simulation, command, resource, reconnect, restart and overload scenarios on isolated services.
- **Changed:** Deleted the raw `/ws` route and its connection manager and removed
  `GET /api/snapshot`. Removed the publisher's legacy batch queue/broadcast, lifecycle-held latest
  compatibility snapshot, `RuntimeExecution.compatibility_snapshot`, the service compatibility
  accessor, simulator snapshot serializer/events and transport-specific simulation timeout.
  Development reset, button and vehicle-signal controls now return the strict acknowledgement
  `{accepted, boot_id}`; authoritative live values continue only through fixed Socket.IO topics.
  Parent review removed initially included current revision/session fields because another queued
  action can finish before the awaiting HTTP coroutine resumes, making those fields identify later
  work. The Socket.IO send timeout now belongs to bounded live-publication
  configuration. Legacy-specific tests were removed and remaining API/runtime tests assert the
  canonical service projection, acknowledgements, precise resource publication and explicit route
  absence.
- **Decisions:** The in-memory simulated runtime remains a selected adapter behind the same
  `ControllerService`, not an independent application owner. Its internal immutable snapshot is
  retained only as the adapter projection/effect result; it is not serialized as a parallel public
  contract. Diagnostic `frame` events remain the sole runtime event rows accepted by the bounded
  trace publisher. HTTP acknowledgements do not merge into frontend live state. No CLI alias,
  compatibility facade, schema platform or unbounded retention was added.
- **Verification:** Full `uv run pytest -q` passed with 499 tests and the one existing
  Starlette/httpx deprecation warning; the count is ten lower because raw-WebSocket manager,
  snapshot-response and compatibility-broadcast tests were deleted with their production code.
  `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus` (61 source files), both generated
  protocol checks, `bash -n scripts/*.sh` and `git diff --check` passed. `pnpm test` passed 30 unit
  and 58 component tests; `pnpm lint`, `pnpm typecheck` and `pnpm build` passed with 2,968 transformed
  modules. PlatformIO passed at 21.5% RAM and 25.6% flash. Dead-path searches find no compatibility
  snapshot, serializer/event, manager, route registration or old timeout symbol in production code.
  A concurrent reset/action regression asserts both responses contain only stable boot-scoped
  acknowledgement facts while the canonical service projection alone reports the final session;
  the post-review simulator/controller/command/publication focus passed 63 tests before the full
  499-test rerun.
- **Browser/soak/physical checks:** T3 product-native preview was retried with `preview_status` and
  `preview_open`, but both returned `Auth required`; no T3 automation is claimed. Under the user's
  offered alternative, final acceptance used an isolated Chrome 150 CDP instance against a
  development backend on port 18100, Vite on 15173 and temporary SQLite. At exactly 800x480, `/dev`,
  `/car`, `/car/drive`, `/car/steering` and `/car/settings` synchronized in light and dark. Every car
  route had no horizontal overflow and zero viewport-clipped controls; `/dev` was intentionally
  vertically scrollable with no horizontal overflow. All four car routes were also visually
  inspected from 800x480 production captures. A development speed PUT for 67.5 returned exactly
  `{accepted: true, boot_id}` and Zustand converged from Socket.IO to 67.5 with no console or network
  errors. A forced backend restart showed `Connected` → `Reconnecting` with `synchronized=false` →
  `Connected`; boot changed from `725eed...` to `a83102...`, transient speed became invalid/0, trace
  rows became 0, the Connected badge was true and the Reconnecting badge false. This directly
  confirms the reported stuck-reconnecting regression is absent. After initial lazy loading, a
  second 24-route same-document development cycle plateaued at exactly one active socket, one
  document, 82 DOM nodes and 1,142 event listeners; repeated-batch GC heap moved 26.3 to 26.7 MB,
  with no console/network errors. The production build transformed 2,968 modules and ran same-origin
  on 18101. Direct loading the same ten route/theme combinations had no horizontal overflow,
  reconnect/unavailable banners, console errors, HTTP errors or network errors. After route modules
  loaded, the second 48-route same-document production cycle plateaued at one document, 190 nodes
  and 998 listeners; GC heap moved 8.3 to 8.5 MB. Isolated port 8030 integration additionally proved
  generated `0x700` ingress and `0x701` desired/observed convergence, repeated maximum-assistance
  set, independent engine staleness, precise settings/profile events to a second Engine.IO client,
  stale-writer winner preservation, full reconnect snapshot without trace replay, reset to a new
  simulation session, restart to a new boot ID, durable settings/profile survival and transient
  telemetry clearing. The Phase 8 backend soak completed 900 mixed commands in 45.02 seconds at
  19.99/s with a deliberately stalled trace subscriber: inbox peak was 1/1,024, maximum latency
  6.06 ms, warnings/overflow/fatal/publisher failures/drops were zero, the saturated peer was
  disconnected, trace ended at 0/2,000 and backend RSS sampled 43.9, 45.8, 46.2 and 46.7 MiB. As
  supporting prior-phase evidence, Phase 7's attached browser ran more than 13 minutes and included
  two 42-second traffic windows. Independently, the user reports their opened application tabs stay
  stable significantly beyond the former 5–10 minute crash. Real CAN TX, physical steering and
  physical read-only checks were unavailable and not enabled.
- **Documentation:** Updated root, coordinator, frontend, simulation, unified-controller,
  car-frontend and assist-curve guidance to describe one controller composition, acknowledgement-only
  development HTTP, Socket.IO/Zustand live ownership and precise Query resource ownership; appended
  the completed cutover note to ADR 0008 and removed active documentation for compatibility
  WebSocket/snapshot behavior.
- **Dependencies/migrations:** None. No dependency, lockfile, SQLite schema, generated live schema,
  custom CAN wire or firmware migration. The development HTTP response shape intentionally removes
  superseded simulator snapshots in favor of acknowledgements.
- **Compatibility/removal:** No compatibility live-read or second-publication path remains. Raw
  `/ws`, `GET /api/snapshot`, snapshot-shaped development responses and all repository internals
  used only by them are removed with explicit 404/route-absence coverage.
- **Remaining:** None for software Phase 8. Optional physical/read-only evidence remains under
  `docs/requires-hardware` and is not blocking; no physical TX or steering authority is granted.
- **Next handoff:** All roadmap phases are verified. Perform the final repository review and report
  the completed architecture, removal, verification and remaining hardware-evidence boundaries.

### 2026-07-15 — Phase 7: bounded reliability and supervised deployment verified

- **Status:** Verified
- **Scope:** Implemented the service-owned failure policy, complete bounded health projection,
  liveness/readiness, deterministic lifecycle, production exposure rules, supervised Pi service and
  simulated soak/restart acceptance.
- **Changed:** Added process-lifetime received/decoded/ignored/malformed counters per CAN network;
  sent/dropped/rate-limited/failed effect counters; bounded controller inbox depth/capacity,
  current/maximum latency, warning count and overflow latch; persistence, publisher, socket,
  trace-ring and fatal/non-fatal diagnostics; and a generated matching frontend contract. Fatal
  reader, any inbox overflow (including non-CAN commands), CAN-effect and steering faults enter the
  ordered safe/terminal path once; emulator
  failure is a typed non-physical adapter fault. Storage failures reject only affected resource
  operations and mark readiness unavailable. Publisher health updates cannot recursively publish,
  topic handoff remains bounded and `controller.health` is coalesced to 1 Hz. Persistence,
  readiness and publisher/socket-only changes commit newer service/health revisions and enter a
  direct one-slot health handoff without publisher recursion. Added exact
  `/health/live` and `/health/ready`; removed the placeholder `/api/health`. Production live mode
  registers no development mutation routes or development CORS, rejects unauthenticated
  non-loopback bind, remains RX-only by default and may serve the built frontend same-origin. The
  live CLI now observes fatal or unexpected owner failure, rejects incomplete Uvicorn startup as
  non-zero for `systemd`, and serves direct SPA routes without masking missing assets or server
  namespaces. Shutdown
  rejects commands, stops readers, commits the safe request, stops publisher/socket tasks, closes
  adapters and verifies joins/cancellation. Added a loopback systemd unit, explicit environment
  template and operator guide. Fixed the frontend trace owner to re-subscribe on every Socket.IO
  connection epoch.
- **Decisions:** Health exposes typed state and bounded counters, never arbitrary log history.
  Process liveness remains responsive when controller readiness fails. Browser/socket disconnect
  does not make the controller unready; persistence failure does. Unknown CAN output outcomes are
  not retried. Current/maximum values and process-lifetime integer counters are retained, while
  trace rows, pending topics, resource changes and per-client Engine.IO packets retain fixed bounds.
  Development routes are absent in live composition, not 503 compatibility facades. The supported
  production boundary is unauthenticated loopback/same-origin; non-loopback deployment requires a
  separate authentication/origin decision. No reverse proxy, monitoring stack, kiosk process or
  automatic capability grant was added.
- **Verification:** Full `uv run pytest -q`: 509 passed with one existing Starlette/httpx
  deprecation warning. Focused post-review reliability/runtime/lifecycle/publication/CLI suites:
  97 passed. `uv run
  ruff check .`, `uv run mypy coordinator/src/e87canbus`, both generated protocol checks,
  `bash -n scripts/*.sh` and `git diff --check` passed. `pnpm test`: 30 unit and 58 component tests
  passed; `pnpm lint`, `pnpm typecheck` and production `pnpm build` passed with 2,968 transformed
  modules. PlatformIO passed at 21.5% RAM and 25.6% flash. Tests cover exact fault/fallback paths,
  persistence isolation, overload latch, fatal CLI exit, live route/CORS/TX exclusion, same-origin
  direct SPA/static serving with honest asset/API 404s, five lifecycle repetitions with fresh boot
  IDs and no owned thread/file-lock leak, bounded publisher/trace behavior, failure-only health
  revision/delivery, nonrecursive publisher diagnostics and reconnect trace subscription.
- **Browser/soak/physical checks:** The T3 browser remained attached to isolated simulated services
  for more than 13 minutes across a deliberate backend restart. Two measured 42-second windows each
  submitted 600 telemetry commands at 14.3/s and 30 settings/profile read pairs; the second added
  100 semantic steering commands. Maximum inbox depth was 1/1,024 and latency 1.920 ms with no
  warning/overflow. The sampled publisher had no failures, drops or transport saturation and had
  coalesced 2,228 health intermediates; trace stayed within 1/2,000 and subscriber ownership moved
  1 → 0 → 1 across route close/reopen. Final counters included 2,305 decoded F-CAN frames, zero
  malformed/ignored frames, 41 sent and 59 rate-limited K-CAN effects, and 2,120 successful steering
  effects. Backend RSS moved from 55.1 MB during warm-up to 39.6 MB and 42.3 MB; the prior process
  was 39.7 MB after 4:35. Browser heap moved from 61.3 MB through 50.7 MB to 53.0 MB with 777 DOM
  nodes and 25 virtual trace rows. The browser replaced state by new boot ID, durable settings
  revision 2 survived, trace re-subscribed after reconnect, the header returned to `Connected`, and
  final live/ready were 200 with non-fatal ready health. The user's independent tabs also remained
  stable well beyond the former 5–10 minute crash window. Real CAN TX, physical steering and
  hardware/vcan checks were unavailable and not enabled; no physical behavior is claimed.
- **Documentation:** Added `docs/reliability.md` with the exact owner/policy table, bounds and soak
  record; updated root, coordinator, frontend and protocol guidance; added `deploy/README.md`, the
  systemd unit and environment template; regenerated `protocol/live-events-v1.schema.json`.
- **Dependencies/migrations:** None. No package/lockfile, SQLite schema, CAN wire or firmware
  protocol migration.
- **Compatibility/removal:** Removed `/api/health` and live-mode development-route facades
  completely. Backend raw `/ws` and `GET /api/snapshot` remain the only pre-existing Phase 8
  compatibility surfaces; no repository frontend consumes them.
- **Remaining:** None for Phase 7. Physical read-only and optional `vcan` evidence may be added when
  available but do not block the software reliability criteria.
- **Next handoff:** Phase 8 should remove the two remaining backend compatibility reads and complete
  cutover/acceptance without weakening health bounds, reconnect resync, shutdown order, trust
  boundary or deny-by-default output authority.

### 2026-07-15 — Phase 6: device roles and simulation converge on shared wire paths

- **Status:** Verified
- **Scope:** Completed physical, emulated, observer and disabled button-pad composition; removed
  presentation-only simulated device health; separated semantic controller commands from explicit
  emulator exercise; and verified narrow routed vehicle simulation and reset lifecycle behavior.
- **Changed:** Added canonical device role/source/desired-observed projection contracts and required
  exactly one selected source per role. Live composition accepts physical, observer or disabled
  button pads; simulation accepts emulated, observer or disabled, with source fixed at startup and
  exposed through the CLI. Physical and emulated inputs use the generated K-CAN `0x700` codec and
  controller routing, and authorized LED effects use the generated atomic `0x701` codec. Observer
  and disabled roles cannot originate input or receive device output. Emulator controls now fail
  when no emulator is selected, while the separately labeled maximum-assistance control issues the
  semantic HTTP command. Device publication exposes source, evidence-backed connection/last-seen,
  desired LEDs, observed LEDs or unknown, and CAN-output faults only. Removed the fake
  online/degraded/offline device model, steering-controller pseudo-device, status mutation API,
  frontend status controls and compatibility imports. Reset reconstructs topology, buses and
  emulators and releases the old session objects. Vehicle speed, RPM, oil and coolant set/silence
  behavior remains on the simulation-only routed CAN boundary. The generic simulator Step action,
  route, command and its residual `next_pressed` transport state were removed; explicit generated
  press/release is the only button-pad emulator input. Emulator indices are fixed to generated
  `LED_COUNT`, including direct node calls.
- **Decisions:** Disabled capabilities are absent from device publication; observer capabilities are
  present but expose unknown connection/observation and no ingress/output authority. An in-memory
  emulator is connected because its endpoint exists and reports observed LEDs only after its
  decoder receives a valid complete output frame. Live physical `last_seen` advances only for a
  valid routed button event; physical connection and LED observation remain unknown because the
  protocol has no acknowledgement. `buttons.state.led_colours` remains controller-desired state,
  while `devices.state` makes desired versus observed explicit. The live envelope remains protocol
  version 1 because this planned Phase 6 projection completed that pre-cutover contract and the
  repository producer, generated schema and sole frontend consumer changed atomically; no old-shape
  facade was retained. Synthetic vehicle identifiers and decoding remain simulation-only. An
  emulated role requires both virtual K-CAN and an explicit simulated K-CAN output grant so it can
  receive controller `0x701` effects; physical output remains separately authorized and default
  deny.
- **Verification:** Full `uv run pytest -q`: 493 passed with one existing Starlette/httpx
  deprecation warning. Focused Phase 6 backend suites: 107 passed. `uv run ruff check .`,
  `uv run mypy coordinator/src/e87canbus`, both generated protocol checks,
  `bash -n scripts/*.sh` and `git diff --check` passed. `pnpm test`: 30 unit and 57 component tests
  passed. `pnpm lint`, `pnpm typecheck` and production `pnpm build` passed; Vite transformed 2,968
  modules. PlatformIO firmware build passed at 21.5% RAM and 25.6% flash, and focused generated
  protocol parity tests passed. Tests cover duplicate/missing authority, source/mode validation,
  observer/disabled non-authority, full emulator encode/bus/router/kernel/effect/decode traversal,
  semantic commands without fabricated input, honest projections, every narrow vehicle signal,
  live-router synthetic-ID rejection, deterministic stale/silence/reset and collection of old
  reset topology/device/endpoints. Frontend coverage explicitly proves observer labeling, unknown
  observation, disabled wire controls and still-available synchronized semantic control.
- **Browser/soak/physical checks:** Final post-review acceptance used direct collaborative-preview
  DOM, live-store and trace instrumentation against a fresh development frontend on port 5190 and
  isolated backend/database on port 8020. Emulated `/dev` synchronized as `Connected`; the header
  exposed Reset with no generic Step control or text, source was `emulated`, the semantic section
  explicitly said it fabricates no input frame, emulator observation was labeled decoded and all
  16 explicit grid controls were enabled. Actual pointerdown/pointerup on Button 0 produced exactly
  `0x700 0001` from `button-pad-emulator`, `0x701 0400000000000000` from `pi` and `0x700 0000` on
  release; mode became manual and desired/observed LEDs both became `[4, 0, ...]`. Clicking semantic
  Enable maximum appended only `0x701 0450000000000000`, with no new `0x700`; maximum became active
  and desired/observed LEDs converged with colour 5 at index 3. After restart in observer
  composition, `/dev` again synchronized as `Connected`, source was `observer`, connection and
  observation were null, unknown observation and emulated-only availability were explicit, no Step
  control existed, all 16 grid controls were disabled and the synchronized semantic control was
  enabled. Semantic maximum returned HTTP 200, changed desired LEDs, left observation null and kept
  trace exactly empty; the backend logged only the expected unavailable-K-CAN-effect warning and no
  failed request. The preview remained automation-capable but reported `visible:false`, so its
  recording and snapshot APIs explicitly failed; no final recording or screenshot is claimed. The
  earlier broader recording at
  `/Users/aidanzealley/.t3/userdata/browser-artifacts/browser-recording-mrm2esrz.mp4` predates Step
  removal and is retained only as pre-review evidence for unchanged pointer/reset/vehicle flows:
  speed, RPM, coolant and oil set/silence projections, reset session 1 to 2, trace clearing and
  documented initial state. The user's separate real application tabs also remained stable
  significantly beyond the former 5–10 minute crash window. Physical read-only and optional `vcan`
  checks were not run because hardware was unavailable and `vcan` is not mandatory. Real CAN TX and
  steering output were not enabled; no physical behavior is claimed.
- **Documentation:** Updated root, coordinator, frontend, simulation and protocol guidance for
  fixed source roles, CLI selection, shared wire paths, desired/observed evidence, semantic versus
  emulator controls and reset behavior. Rewrote the active car-frontend roadmap, device-role,
  foundation, screen, acceptance and agent guidance to remove the retired presentation-health
  contract and route rather than retaining a bannered stale specification. Regenerated the live
  event schema without Step-era state.
- **Dependencies/migrations:** None. No SQLite, lockfile, CAN-wire or firmware protocol migration.
- **Compatibility/removal:** Removed the fake simulator device-status API, models, commands,
  selectors and UI completely. Removed the generic Step API/command/UI and `next_pressed` projection
  completely. No alias, shim or old live-device-shape facade remains. Backend raw `/ws` and
  `GET /api/snapshot` are unchanged pre-existing Phase 8 compatibility surfaces and have no
  frontend consumer.
- **Remaining:** None for Phase 6. Physical read-only and optional `vcan` evidence may be added when
  available but do not block software verification.
- **Next handoff:** Begin Phase 7 without weakening role authority or observation semantics. Make
  failure-only health changes publishable, including device output faults, while avoiding recursive
  effect-failure feedback; retain bounded shutdown and do not authorize physical output.

### 2026-07-15 — Phase 5: browser ownership and reconnect acceptance verified

- **Status:** Verified
- **Scope:** Completed the pending collaborative-browser acceptance for the Phase 5 frontend
  ownership cutover against isolated simulated services in React development and the production
  preview; no implementation changes were required.
- **Changed:** Status and handoff documentation only. The existing one-client Socket.IO transport,
  six-object current live store, separate 2,000-row trace store and TanStack Query durable-resource
  ownership are unchanged.
- **Decisions:** Treated dispatched `blur`, `visibilitychange` and `focus` events as lifecycle-event
  coverage, not proof of genuine operating-system tab backgrounding. Browser heap observations are
  post-warm-up and natural-GC evidence because the preview exposed no forced-GC control. React
  development performance measures were separated from application-owned retained structures.
- **Verification:** The previously recorded repository-wide backend/frontend checks remain green.
  A fresh production build passed with 2,968 modules. Browser instrumentation of the actual client,
  after deterministic teardown/restart, found one connected Socket.IO client with the same client
  ID and an open Manager throughout route and traffic checks; exactly one listener remained for
  each of `connect`, `connect_error`, `disconnect` and the nine fixed server events. The live store
  retained exactly six current topic objects. Query cache size settled at exactly two durable roots:
  steering-profile collection and application settings.
- **Browser/soak/physical checks:** The development `/dev` view synchronized as `Connected`,
  directly covering the snapshot-before-local-connect badge race. Thirty `/dev` to `/car/drive`
  SPA cycles, including dispatched lifecycle events and trace close/reopen, retained the same socket
  and listener counts, two Query entries and 592 final `/dev` DOM nodes; trace cleared on close and
  subscribed fresh on return. Two 500-command development windows retained 360 then 700 trace rows,
  771 DOM nodes in both windows and 29,294 then 26,769 performance entries, of which 29,005 and
  26,474 were React development component measures. Heap moved from 53.0 to 76.6 MB in the first
  window and naturally fell to 69.0 MB in the second, with no acceleration or monotonic retained
  growth. In production, 30 equivalent route cycles ended `Connected` with two Query entries, 612
  DOM nodes, 36 performance entries and 51.3 MB heap. Successive 500-command windows retained 560
  then 1,120 trace rows, held DOM at 792 and performance entries at 256 (the browser's 250-resource
  buffer plus non-resource entries), while heap reached 57.7 MB then naturally fell from 57.8 to
  55.1 MB. A further 1,000 commands capped trace at exactly 2,000, with DOM still 792, performance
  entries still 256, heap 56.5 MB and connection still synchronized. `/dev` and `/car/drive` visual
  snapshots rendered without console errors at the requested 800x480 freeform setting; the preview
  reported 960x576 after scaling. Stopping the backend changed `/dev` to `Disconnected`, marked
  engine values stale, devices offline/unavailable, removed the network topology and cleared trace;
  restarting it returned the existing page to `Connected`, cleared stale labels and retained a
  fresh zero-row trace. The user's separate real application tabs also remained stable significantly
  beyond the former 5–10 minute crash window. No forced GC or genuine OS backgrounding was
  available. Real CAN TX was unavailable and not enabled; no physical evidence is claimed.
- **Documentation:** Updated this status table, current handoff and newest-first verification entry.
- **Dependencies/migrations:** None. The isolated clean SQLite database returned settings normally;
  an attached long-running development backend's settings 503 was traced to its tracked SQLite file
  being overwritten/restored while open by automated tests, not to a Phase 5 frontend defect.
- **Compatibility/removal:** No compatibility path was added. Backend raw `/ws` and
  `GET /api/snapshot` remain Phase 8 external-consumer compatibility only; no frontend facade or
  consumer remains.
- **Remaining:** None for Phase 5.
- **Next handoff:** Begin Phase 6 from the verified single-owner frontend boundary. Keep dashboard
  observation non-authoritative, distinguish semantic commands from emulator actions and do not
  infer physical acknowledgement or enable real CAN TX.

### 2026-07-15 — Phase 5: frontend ownership cut over; browser verification pending

- **Status:** Implemented
- **Scope:** Replaced repository-owned frontend raw-WebSocket/snapshot-cache ownership with one
  Socket.IO-to-Zustand live path, a separate bounded trace store and TanStack Query-only HTTP
  ownership across `/dev` and `/car`. Browser acceptance remains incomplete.
- **Changed:** Added one application-scoped Socket.IO transport outside React, an idempotent
  lifecycle-only provider, complete-snapshot/boot replacement, explicit protocol incompatibility,
  strict per-topic revision decisions and deterministic reconnect reconciliation. Added a Zustand
  current-state store for connection, boot/topic revisions and the six fixed projections, plus a
  separate 2,000-row trace store subscribed only while trace UI is mounted. Durable queries now have
  stable exact keys, explicit stale time and disabled focus/reconnect refetch; precise resource
  events invalidate only their matching keys and each accepted connection snapshot reconciles the
  known durable roots exactly once per real connection epoch, including when the server snapshot is
  observed before the local Socket.IO `connect` event. Simulation and steering actions use TanStack mutations with initiating
  control pending state; settings/profile responses replace exact cache values. Car and workbench
  components use narrow live selectors and no longer share a whole-snapshot context.
- **Decisions:** A same-boot stale/duplicate topic is ignored without resync traffic; only a boot
  mismatch requests `controller.resync`, and only a complete snapshot may replace boot identity or
  declare synchronization. The singleton defers zero-owner teardown by one microtask so React Strict
  Mode cleanup/setup reuses the same client and listeners; explicit teardown remains deterministic.
  Disconnected screens retain durable Query resources and navigation but mask every current live
  observation as unavailable. As a small Phase 4 contract correction discovered during this phase,
  the generated live contract now constrains steering-curve `schema_version` to literal `1`, matching
  the existing TypeScript and validated domain contract.
- **Verification:** Full `uv run pytest -q`: 503 passed with one existing Starlette/httpx
  deprecation warning. `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus`, both generated
  protocol checks, `bash -n scripts/*.sh` and `git diff --check` passed. `pnpm test`: 30 unit and 57
  component tests passed. `pnpm lint`, `pnpm typecheck` and production `pnpm build` passed; Vite
  transformed 2,968 modules. Focused tests cover atomic boot replacement, stale/duplicate rejection,
  boot resync, incompatibility, snapshot-before-connect ordering, exactly-once connection-epoch
  reconciliation, one listener per event, Strict Mode remount, explicit teardown,
  disconnect/synchronization masking across `/car` and `/dev`, 2,000-row trace capacity, exact
  resource invalidation, steering draft/provenance safety, settings authority/retry/conflict
  retention, exact simulation set/silence actions, action-local pending state and adjacent-selector
  rerender isolation.
- **Browser/soak/physical checks:** The required in-app browser could not be selected because its
  inventory returned empty; the parent T3 collaborative preview separately returned `Auth required`.
  Therefore `/dev`/`/car` visual regression, route-cycle DOM/performance counts and browser post-GC
  heap behavior were not run and Phase 5 is not Verified. A real Socket.IO client against the
  simulated Uvicorn service processed 100 alternating HTTP signal commands, retained exactly one
  listener for each of the nine server events, received one snapshot, 50 bounded trace batches/198
  rows, four engine and four vehicle publications, and finished with zero receive/send-buffer
  entries; its post-GC Node heap was 9,436,576 bytes. This is transport evidence, not a substitute
  for browser evidence. Real CAN TX was unavailable and not enabled; no physical evidence claimed.
- **Documentation:** Updated frontend, root, simulation and coordinator guidance for
  Socket.IO/Zustand/Query ownership, Engine.IO reconnect/heartbeat behavior and Phase 8 backend
  compatibility; updated this status/handoff record.
- **Dependencies/migrations:** Added frontend runtime dependency `socket.io-client` 4.8.3 and its
  locked Engine.IO/parser dependencies. Regenerated `protocol/live-events-v1.schema.json` for the
  literal-v1 curve-schema correction. No SQLite or CAN protocol migration.
- **Compatibility/removal:** Removed all frontend raw `/ws`, `GET /api/snapshot`, snapshot Query
  key/cache/reducer, component listener, CarData context/provider, old reconnect/heartbeat module and
  broad simulator command owner. Backend raw `/ws` and snapshot reads remain only for Phase 8
  external-consumer compatibility. No frontend facade or alias remains.
- **Remaining:** Run and record the phase's collaborative-browser development and production
  regression/memory evidence, then mark Phase 5 Verified if bounded. No code criterion is knowingly
  outstanding.
- **Next handoff:** Authenticate/attach the parent collaborative preview and run the exact Phase 5
  browser matrix before assigning Phase 6. Use the existing store/transport inspection points; do
  not reintroduce a raw socket or snapshot Query cache to gather evidence.

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
