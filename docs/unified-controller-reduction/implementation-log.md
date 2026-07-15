# Unified controller reduction implementation log

This is the durable handoff for the deletion-led simplification pass. It records measured reduction,
behavior preserved and any target that could not be met safely. It must not count moved, generated
or reformatted code as simplification.

## Phase status

| Phase | Status | Last entry | Production reduction | Notes |
|---:|---|---|---:|---|
| 1 — Baseline and deletion map | Verified | 2026-07-15 | 0 | Baseline, seven flow maps and candidate ledger recorded |
| 2 — Contract/model consolidation | Verified | 2026-07-15 | 90 | Typed values cross framework boundaries directly; target variance accepted |
| 3 — Runtime/service reduction | Verified | 2026-07-15 | 302 | One shared adapter update and projection path |
| 4 — Publication/diagnostics reduction | Verified | 2026-07-15 | 327 | Decision-useful health and one publisher diagnostic owner |
| 5 — Composition/frontend seams | Verified | 2026-07-15 | 202 | Explicit constructors and one application-lifetime transport owner |
| 6 — Test-suite reduction | Verified | 2026-07-15 | 0 | 323 test lines and three test files removed |
| 7 — Cutover/acceptance | Verified | 2026-07-15 | 100 | Final dead-path removal; cumulative production net -1,021 |

## Current handoff

All seven phases are verified on the controlling branch through Phase 7 commit
`6bd285b949ea5f55067e09cd2ea4ab9fc33e1bed`. The
roadmap base remains `a31d2f8016bb3d6766425ae5fb244a5058fecc63`; the direct cumulative production
diff is +467/-1,488, net -1,021: backend +403/-1,225, net -822, and frontend +64/-263,
net -199. The surviving suite has 31 backend files/485 cases/7,325 lines, 6 frontend unit
files/30 cases/847 lines and 16 frontend component files/55 cases/2,451 lines. Preserve the one
ordered owner, explicit live/simulated constructors, direct `DeviceSource` validation, default
no-live-TX policy, application-lifetime frontend transport, strict public contracts and every
bounded inbox/publication/trace/store/peer behavior. No compatibility path or deferred reduction
remains. Interactive browser and physical-CAN evidence were unavailable and are not inferred from
the automated and isolated-service acceptance.

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
`Implemented` requires a measurable simplification and focused checks. `Verified` requires all
phase criteria, repository-wide checks relevant to the change and honest before/after accounting.

## Entry template

Add entries newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** Exact slice attempted and behavior intentionally left unchanged.
- **Deletion hypothesis:** Concepts/layers/files expected to disappear and why they are redundant.
- **Production accounting:** Base commit; backend/frontend lines added/deleted/net; files added,
  deleted and touched. Report tests/docs/generated separately.
- **Cognitive accounting:** Named concepts, flow hops and contract copies before/after.
- **Changed:** Important deletions, necessary additions and public-contract consequences.
- **Protected behavior:** Bounds, ownership, reconnect, safety and failure behavior re-proved.
- **Tests:** Retained contract tests; tests removed with deleted internals; new tests and why needed.
- **Test accounting:** Test files/lines/count/runtime before/after; value classifications retained;
  obsolete/private/impossible-state tests removed.
- **Verification:** Exact focused and repository-wide commands, counts, warnings and failures.
- **Browser/soak/physical checks:** Evidence run, prior evidence still applicable, or honestly not run.
- **Dependencies/migrations:** None, removals, or additions with justification.
- **Compatibility/removal:** Facades/aliases removed; none may be introduced silently.
- **Target variance:** Budget met, exceeded or blocked; explain variance without cosmetic accounting.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** Most important deletion opportunity, risk or prerequisite.
```

## Entries

### 2026-07-15 — Final controlling review: no further scoped fix required

- **Status:** Verified
- **Scope:** Audited the roadmap-base-to-HEAD diff for dead symbols, residual legacy surfaces,
  duplicated bounds/state ownership, obsolete compatibility, and deferred deletion conditions.
  The audit found no concrete production, test, or compatibility fix; no further deletion or fix is
  deferred.
- **Accounting:** Production remains +467/-1,488, net -1,021 from roadmap base
  `a31d2f8016bb3d6766425ae5fb244a5058fecc63`: backend +403/-1,225, net -822, and frontend
  +64/-263, net -199. This final review changes production +0/-0, tests +0/-0, generated artifacts
  +0/-0 and temporary compatibility +0/-0; it updates documentation only. All exact prior phase
  accounting remains unchanged.
- **Compatibility/removal:** No compatibility path remains and no removal or production-code
  deletion is deferred. No consumer, objective removal condition, or later phase exists to record.
- **Verification:** Reviewed the base-to-HEAD diff and repository status and ran dead-symbol,
  legacy-surface, bounds-owner and documentation-diff audits. No test, lint, typecheck, build,
  browser, soak, or physical suite was rerun for this documentation-only correction.

### 2026-07-15 — Phase 7: integrated cutover meets the honest reduction target

- **Status:** Verified
- **Scope:** Performed the final dead-symbol, forwarding-facade, compatibility, route-authority,
  diagnostics and test-seam audit; removed the last production-only diagnostic archaeology and
  nested import forwarding files; then ran repository-wide and isolated-service acceptance.
  Controller state, effect behavior, public payloads, routes, queues, stores, schemas, lifecycle,
  frontend rendering and configuration were intentionally unchanged.
- **Deletion hypothesis:** Phase 4 removed the last production/public consumer of process-lifetime
  effect outcome counters, but `EffectExecutionDiagnostics`, its empty value, aggregation function,
  `EffectExecutor.diagnostics` accessor and seven private counters remained solely for four private
  test assertions. Eighteen nested one-line `index.ts` barrels added import forwarding without a
  contract or ownership boundary. Two TypeScript exports had no consumer. These were deletable
  without replacing their behavior or creating a new abstraction.
- **Production accounting:** Phase base
  `55357e20c7a461b910110a7e291ab8bbea7790c2`. Backend production is +2/-80, net -78 across
  `coordinator/src/e87canbus/output.py` +1/-79 and `cli/main.py` +1/-1; frontend production is
  +18/-40, net -22 across 27 touched
  paths. Frontend API/editor files are `api/steering.ts` +0/-1,
  `steering-curve-editor/store.ts` +0/-3, `SteeringCurveEditor.tsx` +8/-8 and
  `curve-actions/CurveActions.tsx` +2/-2. Simulator consumer files are
  `SimulatorNeoTrellis.tsx` +1/-1, `SimulatorTrace.tsx` +2/-2,
  `SimulatorWorkbench.tsx` +3/-3, `can-trace-table/CanTraceTable.tsx` +1/-1 and
  `simulator-toolbar/SimulatorToolbar.tsx` +1/-1. The other 18 frontend production paths are the
  deleted one-line nested `index.ts` barrels under `simulator-workbench/components` (8) and
  `steering-curve-editor/components` (10). Total production is +20/-120, net -100; 18 files are
  deleted, 0 added and 29 production paths touched. Tests are +5/-9, net -4 across
  `coordinator/tests/test_output.py` +0/-4,
  `frontend/src/components/simulator-workbench/SimulatorWorkbench.test.tsx` +3/-3 and
  `live-availability.test.tsx` +2/-2. Documentation is this log +144/-11, net +133; generated
  artifacts +0/-0; deployment/scripts +0/-0; firmware +0/-0; temporary compatibility +0/-0.
  Cumulatively from roadmap base `a31d2f8`, the direct production diff is +467/-1,488, net -1,021:
  backend +403/-1,225, net -822, and frontend +64/-263, net -199. Cumulative tests are
  +347/-757, net -410; generated live schema +12/-244, net -232; documentation +1,040/-26,
  net +1,014; deployment/scripts, firmware and temporary compatibility remain net zero. Current
  physical production is 7,828 backend lines/61 files and 8,971 frontend lines/114 files, versus
  8,650/61 and 9,170/134 at the roadmap base. The largest apparent additions are 18 direct import
  path replacements, one direct transmitter call replacement and one corrected CLI help line; they add no logic or concept and
  enable deletion of the 18 forwarding files and the retired diagnostics path.
- **Cognitive accounting:** Removed named production concepts are `EffectExecutionDiagnostics`,
  `EMPTY_EFFECT_DIAGNOSTICS`, `add_effect_diagnostics`, `EffectExecutor.diagnostics`, seven private
  outcome counters, `SteeringCurveInterpolation`, `selectPending` and 18 forwarding modules. Added
  concepts: 0. The in-repository directory-import consumers were changed to direct component-file
  imports in the same phase; the barrels were not unconsumed files, and no compatibility import was
  retained. Operational/lifecycle/publication/frontend socket owners remain 1/1; queues/stores
  remain one controller inbox, latest-topic map, resource deque, trace deque, frontend trace ring
  and one finite Engine.IO queue per peer. Schemas, runtime state owners and public contract copies
  added/removed in this phase: 0/0. Across the programme, named result/projection/selection/
  diagnostics/lifecycle concepts removed include the Phase 3 result/snapshot/reader layers, Phase 4
  publication and health mirrors, Phase 5 selection/provider/transport-owner layers and this final
  effect diagnostic. Contract copies removed are two resource/live structural copies in Phase 2
  and one publisher-health representation in Phase 4; no replacement schema platform exists.
- **Final flow accounting:** The seven Phase 1 normal paths change in file hops as follows:
  SocketCAN observation 7 -> 7, semantic command 9 -> 8, simulation action 10 -> 9, commit-to-topic
  6 -> 6, reconnect-to-Zustand 4 -> 4, durable mutation 8 -> 8 and startup/shutdown 7 -> 7.
  Every unchanged file count crosses fewer named transformations: reader/result/projection rewraps,
  repeated Pydantic reconstruction, publisher-health copies, resource dictionaries, generic
  composition selection, React transport ownership or effect diagnostics were removed. CLI
  composition is preset/selection/generic-builder -> explicit constructor; browser startup is
  provider/reference-counted-owner/transport -> application-owned transport. No flow was shortened
  by hiding a value in `Any`, a generated layer or a generic framework.
- **Changed:** `EffectExecutor` now records only bounded rate-window timestamps needed to enforce
  output safety and returns explicit execution failures; it no longer retains unused historical
  outcome totals. Observable unavailable-capability logging, encoded output, rate limiting,
  uncertain-send reservation, CAN failure and steering failure behavior remain. Nested frontend
  consumers and three Vitest mocks now name their canonical component files directly. No route,
  socket event, payload, configuration option, queue, schema, owner, dependency or generated file
  changed.
- **Protected behavior:** One ordered bounded owner still handles frames, timers, commands, faults
  and shutdown. Live and simulated compositions use one service and production codecs/effects;
  default live remains unable to transmit. HTTP command/resource authority and Socket.IO live
  authority remain non-overlapping. Complete reconnect snapshots, new-`boot_id` replacement,
  topic-local revisions, singleton frontend listeners, resource invalidation, trace opt-in/reset/
  2,000-row retention, eight-resource retention, latest-topic coalescing, 1,024-input capacity,
  finite peer queues, slow-peer isolation, readiness/fatal truth and shutdown deadlines all pass.
- **Tests:** Removed four assertions against the retired private counter accessor. The same tests
  retain the meaningful guarantees: deny-by-default output and explicit grants are safety;
  network-window exhaustion and no replay are concurrency/boundedness; exact LED bytes are domain/
  integration behavior; distinct returned CAN/steering failures are current failure contracts.
  Direct-import mock replacements preserve the existing disconnected workbench regression. No test
  case/file was added or removed, no production seam was added for a test, and no safety, public,
  boundedness, regression, domain or integration cluster was weakened.
- **Test accounting:** Tracked tests change from 53 files/10,627 lines to 53 files/10,623 lines.
  Backend remains 31 files/485 cases and changes 7,329 -> 7,325 lines; full runtime was 10.58s.
  Frontend remains 6 unit files/30 cases/847 lines and 16 component files/55 cases/2,451 lines;
  runtimes were 238ms and 3.72s. Test declarations remain 570 total. Test/doc/generated deletion is
  not credited to the production target.
- **Verification:** Focused output/live/simulation/service coverage passed 61 cases in 1.57s. Full
  `uv run pytest -q` passed 485 tests in 10.58s with the existing Starlette/httpx deprecation
  warning. `uv run ruff check .`, mypy over 61 source files, both generated checks,
  `bash -n scripts/*.sh` and `git diff --check` passed. Frontend `pnpm test` passed 30 unit and 55
  component tests; `pnpm lint`, `pnpm typecheck` and `pnpm build` passed with 2,948 transformed
  modules. An initial root `pnpm` command failed before execution because the manifest is under
  `frontend`; the package-local commands passed. An initial frontend typecheck correctly exposed
  directory imports through the deleted barrels; consumers and three matching mocks were updated,
  after which all checks passed. Dead-symbol/import/active-document searches find none of the
  removed diagnostic, result, selection, transport-owner or compatibility names and no raw `/ws`,
  snapshot or curve-state live path.
- **Browser/soak/physical checks:** Browser-control setup, one required troubleshooting pass and
  discovery returned no available browser, so no fresh interactive route/theme/800x480 DOM or heap
  evidence is claimed. The unchanged 16-file DOM route/component suite passed. An isolated
  simulated service processed 300 HTTP speed commands at 1,154.5/s while Engine.IO polling was
  trace-subscribed; an authoritative resync returned ready true, fatal false, inbox depth 0/1,024,
  no latency warning/overflow, publisher failures/resource drops/trace drops zero, 274 received
  trace rows and one durable resource event. Abandoned polling sessions produced one bounded peer
  saturation without blocking the controller. RSS was 62,880 KiB. Clean shutdown/restart changed
  `boot_id` from `9881ab6b...` to `388b4bf3...` and returned ready true/fatal false. Two preliminary
  high-level client attempts failed because optional `websocket-client`/`requests` packages are not
  installed; the dependency-free raw Engine.IO polling acceptance then passed. Firmware, real CAN,
  physical steering and physical output were untouched and remain unavailable/unclaimed.
- **Dependencies/migrations:** None. No dependency, lockfile, SQLite schema, CAN protocol, firmware,
  generated artifact, deployment file or build input changed. Temporary SQLite and build artifacts
  were removed/restored.
- **Compatibility/removal:** None retained or introduced. The deleted frontend forwarding files had
  only in-repository consumers, all updated directly in this phase; they have no external import
  contract. Current Socket.IO v1, semantic HTTP resources/commands and canonical `e87canbus run`
  are present contracts, not compatibility. There is no consumer, temporary reason, objective
  removal condition or deferred phase to record.
- **Target variance:** Phase 7 removes 100 net production lines and 18 production files through
  genuine dead state/diagnostic and forwarding-layer deletion. Cumulative production is net
  -1,021, exceeding the approved 1,000-line target by 21 without moving the 85-line frontend test
  fixture, counting tests/docs/generated output, compressing formatting, weakening types or hiding
  complexity. The baseline predicate's test-fixture classification is left unchanged rather than
  exploited.
- **Remaining:** No roadmap production, compatibility or verification deletion remains. The system
  is not claimed minimal: controller/runtime, bounded publication, strict boundary schemas, SQLite
  concurrency, explicit mode composition and frontend state owners remain because each protects a
  current ownership, safety, retention or public-contract guarantee. Fresh interactive browser and
  physical-vehicle acceptance remain evidence limitations, not deferred code removal.
- **Next handoff:** Phase 7 was committed as
  `6bd285b949ea5f55067e09cd2ea4ab9fc33e1bed`. Final controlling review found no concrete
  production, test or compatibility fix and no further deletion or fix is deferred. Future changes
  should reject any second state owner, live transport, unbounded retention path, compatibility
  facade or test-only production diagnostic seam.

### 2026-07-15 — Phase 6: behavior-focused suite replaces implementation archaeology

- **Status:** Verified
- **Scope:** Reduced backend and frontend tests after the production boundaries stabilized. The
  controller, runtime, simulation, publication, public HTTP/Socket.IO contracts, durable resources,
  frontend behavior and all production code were intentionally unchanged.
- **Deletion hypothesis:** A predecessor-name inventory, deleted result/snapshot-shape assertions,
  private duplicate-trace assertions, one-test-per-bus-method coverage, tautological configuration
  assertions, repeated retired-route probes, unexecuted standalone component files and a same-branch
  theme matrix added maintenance effort without protecting a distinct supported behavior.
- **Production accounting:** Phase base
  `3c33e2fc264212de39e7d8e3dffb5f35955a3d65`. Backend production +0/-0; frontend production +0/-0;
  production files added/deleted/touched 0/0/0. Tests are +38/-361, net -323 across ten touched
  paths, with three files deleted: backend +5/-157, net -152 across seven paths and frontend
  +33/-204, net -171 across three paths. Backend file accounting is `test_architecture.py` +0/-14,
  `test_command_api.py` +3/-12, `test_config.py` +0/-19, `test_events.py` +0/-34,
  `test_simulation_bus.py` +2/-39, `test_simulation_runtime.py` +0/-10 and deleted
  `test_steering.py` +0/-29. Frontend file accounting is `CarFoundation.test.tsx` +33/-39 and the
  deleted `DriveTemperatureGauge.test.tsx` +0/-133 and `RpmBar.test.tsx` +0/-32. Documentation is
  this log +105/-10, net +95; generated artifacts +0/-0; temporary compatibility +0/-0. Cumulatively from roadmap
  base `a31d2f8`, production remains +454/-1,375, net -921 (backend +407/-1,151, net -744;
  frontend +47/-224, net -177), while tests are +342/-748, net -406 (backend +305/-501, net -196;
  frontend +37/-247, net -210). There are no production additions; the largest test addition is
  +33 in `CarFoundation.test.tsx`, consolidating the distinct drive-gauge Celsius-position,
  critical accessible-status and redline motion-safe strobe checks before deleting 165 lines of
  unexecuted standalone tests.
- **Cognitive accounting:** Production owners, concepts, flow hops, queues, schemas and contract
  copies added/removed: 0/0. Removed test-only concepts are the pre-kernel obsolete-name inventory,
  deleted simulation result shape, private second-trace-storage checks, separate send/receive bus
  method cases, duplicated hard-coded protocol/config facts, repeated historical route probes, two
  dead standalone component clusters and a light/dark execution of the same assertion branch.
  In-memory network delivery is now one peer-delivery/sender-isolation contract. Current public,
  safety, concurrency/bounds, regression, domain and integration owners remain directly tested.
- **Changed:** Deleted the fully superseded three-case `test_steering.py`; curve interpolation,
  endpoint and manual clamp behavior remains covered at the curve-domain/controller boundaries.
  Deleted trivial frozen-value field-copy assertions and obsolete production-name searches. Removed
  assertions that the Phase 3 result/snapshot and trace duplication had not returned. Consolidated
  four private bus mechanics into one delivery contract and retained topology isolation, global
  order and ring overflow. Removed tautological valid-config cases and a hard-coded custom-ID copy;
  invalid bounds, generated definition currentness and codec vectors remain. The command API keeps
  strict-body validation and the current negative HTTP active-state ownership guarantee without
  probing every historical mutation route. Frontend critical-status, Celsius-position and active
  redline motion-safe-strobe evidence now lives in the existing component boundary; duplicated/dead
  files and same-branch theme executions are gone.
- **Protected behavior:** Retained one-owner order, inbox overflow and fatal-result truth; no-TX and
  capability validation; production CAN vectors and simulation parity; strict HTTP/Socket.IO
  contracts; complete reconnect/`boot_id` replacement and singleton listeners; peer/latest/resource/
  trace bounds and slow-client isolation; SQLite conflict winner preservation; lifecycle readiness,
  shutdown and cleanup; route behavior, unavailable-state masking, text alternatives, critical
  status and the redline shift strobe; curve, freshness and device-domain behavior.
- **Tests:** Retained clusters map to the rubric: command/resource/socket contracts are public
  behavior; output grants/failsafe/fatal rejection are safety; inbox/publication/store/listener and
  deadline tests are concurrency/bounds; reconnect, lifecycle leak and retained-state cases are real
  regressions; curve/codecs/freshness/device cases are domain examples; API/runtime/publication/DOM
  route and screen tests provide integration confidence. Negative route tests remain only for the
  active-live-state HTTP authority boundary and retired snapshot/raw-WebSocket surfaces whose
  restoration would overlap Socket.IO authority or be masked by SPA routing. No test was replaced
  one-for-one and no production seam was added.
- **Test accounting:** Backend changes from 32 files/498 cases/7,481 lines to 31 files/485 cases/
  7,329 lines; collection changes from 0.38s to 0.35s and full execution from 9.96s to 10.49s, normal
  timing variance rather than a claimed speedup. Frontend unit remains 6 files/30 cases/847 lines;
  runtime changes from 211.8ms to 207.9ms. Executed frontend components change from 16 files/57
  cases/2,457 lines to 16 files/55 cases/2,451 lines and 4.44s to 3.97s. Two additional tracked but
  unexecuted component files (165 lines/six declarations) were deleted, so total tracked frontend
  tests change from 24 files/3,469 lines to 22 files/3,298 lines. Total tracked tests change from 56
  files/10,950 lines to 53 files/10,627 lines. Firmware has no test files and was untouched;
  browser/integration has no standalone tracked suite beyond the DOM component/route tests.
- **Verification:** Focused changed backend tests passed 97 cases in 1.00s and the consolidated
  component file passed four cases in 1.13s. Full `uv run pytest -q` passed 485 tests in 10.49s with
  the existing Starlette/httpx warning. `uv run ruff check .`, mypy over 61 source files, both
  generated checks, `bash -n scripts/*.sh`, `git diff --check`, frontend `pnpm test` (30 unit plus
  55 component), `pnpm lint`, `pnpm typecheck` and `pnpm build` (2,966 modules) passed. One focused
  pnpm invocation from the repository root failed before collecting tests because the manifest is
  under `frontend`; the same command was rerun there and passed. Dead-file/symbol searches found no
  active reference to the removed test files, cases or predecessor symbols.
- **Browser/soak/physical checks:** Browser runtime discovery returned no available browser, so no
  new interactive browser evidence is claimed. Complete route/component regressions passed and no
  production frontend behavior changed. No soak or physical check was needed for test-only changes;
  firmware, CAN TX and physical steering were untouched and remain unclaimed.
- **Dependencies/migrations:** None. No dependency, lockfile, database schema, CAN protocol,
  firmware, generated artifact or build input changed.
- **Compatibility/removal:** None. No facade, alias, deprecated path, forwarding layer or temporary
  compatibility is retained or introduced; there is therefore no consumer, removal condition or
  deferred removal phase.
- **Target variance:** Phase criterion is met with 323 net test lines, 13 backend cases, two executed
  frontend cases and three tracked files removed. Production remains unchanged as required. The
  result does not claim reduction from generated output, moved code, weakened types or lost safety
  coverage.
- **Remaining:** None for Phase 6. Runtime improvement is not claimed because backend timing varied
  upward even though the frontend unit and component timings decreased.
- **Next handoff:** Phase 7 should run integrated acceptance and audit residual production/test
  paths against the cumulative -921 production-line reduction, retaining the reduced suite's public,
  safety, bounds, regression, domain and integration coverage.

### 2026-07-15 — Phase 5: explicit composition and application-owned transport

- **Status:** Verified
- **Scope:** Replaced generic live/simulated selection mirrors with two explicit constructors and
  moved the singleton browser transport to application lifetime. Controller, runtime, publication,
  live/durable state, trace, resource, route and visual behavior were intentionally unchanged.
- **Deletion hypothesis:** CAN adapter kinds, steering capability selection, device-selection tuples
  and a mode-switched builder copied variability already fixed by the live and simulated runtime
  owners. `LiveDataProvider` and `createLiveTransportOwner` added a second reference-counted React
  lifecycle around an application-wide transport. Once startup occurs before the React tree, the
  transport's separate start/stop seam is test-only.
- **Production accounting:** Phase base
  `412e4140d6294245cdbe91d95aa9e0f0709aac37`. Backend production is +111/-222, net -111 across four
  touched files: `api/main.py` +21/-8, `cli/main.py` +22/-21, `composition.py` +68/-187 and
  `device.py` +0/-6. Directory totals are API +21/-8 and backend root +90/-214. Frontend production
  is +37/-128, net -91 across five files: `live/transport.ts` +31/-111, `main.tsx` +6/-6 and the
  deleted `components/live-data-provider/LiveDataProvider.tsx` +0/-10 plus `index.ts` +0/-1;
  `api/simulator.ts` is unchanged after review retained its useful typed request helper. Total
  production is +148/-350, net -202; 2 files deleted, 0 added and 9 touched. Current production is
  7,906 backend lines/61 files and 8,993 frontend lines/132 files. Tests are +56/-135, net -79
  across seven files: `test_cli_main.py` +6/-0, `test_controller_service.py` +22/-39,
  `test_live.py` +13/-32, `test_live_publication.py` +3/-3, `test_profile_api.py` +2/-4,
  `test_simulator_api.py` +6/-14 and frontend `live/transport.test.ts` +4/-43. Backend tests total
  +52/-92, net -40; frontend tests total +4/-43, net -39. Documentation is this log +115/-9,
  net +106; generated artifacts +0/-0; temporary compatibility +0/-0. Cumulatively from roadmap
  base `a31d2f8`, production is +454/-1,375, net
  -921: backend +407/-1,151, net -744, and frontend +47/-224, net -177. The largest additions are
  +68 in `composition.py` for direct live/sim constructors and safety validation, +31 in
  `transport.ts` where existing listener setup now executes at construction, and +22 in the CLI for
  direct source selection/reporting. They replace larger selection and lifecycle layers in this
  phase; no later deletion is required to justify them.
- **Cognitive accounting:** Operational, lifecycle, publication and frontend socket owners remain
  1/1. Removed production concepts: `CanAdapterKind`, `SteeringCapability`, `CanAdapterSelection`,
  `CompositionSelection`, `DeviceAdapterSelection`, `live_selection`, `simulated_selection`, the
  generic `build_controller_service`, `LiveDataProvider`, `createLiveTransportOwner`, its owner/
  trace-owner counters and teardown generation, and transport start/stop lifecycle state. Added
  concepts are only the named mode boundaries `build_live_controller_service` and
  `build_simulated_controller_service`. CLI composition changes from CLI -> preset selection ->
  dataclass validation -> generic builder -> runtime to CLI -> explicit constructor -> runtime.
  Browser startup changes from main -> React provider -> reference-counted owner -> transport to
  main -> transport. Runtime queues, publication stores, public schemas, contract copies, state
  owners and route count added/removed: 0/0.
- **Changed:** `AppConfig` now directly determines enabled physical or virtual networks. One
  `DeviceSource` argument selects the only button-pad authority, making duplicate/missing role
  selections unrepresentable. Constructors reject physical/emulated mode conflicts, unavailable
  K-CAN authority and output grants before service startup; the canonical live runtime continues to
  reject configured TX without a grant. The CLI constructs that explicit service once so dry-run
  validates the same selection without changing environment or the global ASGI app; normal startup
  passes the already-built service into the API. The frontend
  creates its singleton transport once beside the Query client before React renders; listener setup,
  reconnect reconciliation, trace reference counting and stores remain in `transport.ts`.
- **Protected behavior:** Default live composition has zero TX grants and no steering actuator;
  explicit test TX remains rate-limited; simulation still uses production codecs/transitions/
  effects; live/simulated and observer/disabled roles remain supported; invalid authority/output
  selections fail before startup; dry-run remains side-effect-free; one controller service and
  lifecycle remain. Socket snapshot,
  reconnect, `boot_id`, topic-revision, resource invalidation and trace subscribe/unsubscribe/reset/
  2,000-row bounds remain. Current live state remains Zustand-only, durable resources Query-only,
  selectors narrow, mutation pending/error/conflict state local, and 800x480 light/dark route code
  unchanged. No UI control was added.
- **Tests:** Retained CLI/API route and mode behavior; default-no-TX, explicit-grant, invalid-role and
  missing simulated-output safety; lifecycle/thread cleanup; simulation production-path domain
  coverage; socket singleton/listener, reconnect, snapshot-before-connect, resource invalidation,
  trace cleanup/bounds; store merge/revision; route/layout/theme and localized mutation states.
  CLI coverage now proves dry-run preserves the global app and both relevant environment variables
  while the invalid physical-in-simulation dry-run still fails.
  Removed three tests that manufactured duplicate/missing selection tuples, because one typed
  `DeviceSource` makes those private states unrepresentable. Removed the private reference-counted
  owner/Strict-Mode test after transport startup moved outside React; the surviving boundary test
  proves exactly one socket/listener set, while route tests protect application behavior.
- **Test accounting:** Tracked tests remain 56 files and change from 11,029 to 10,950 physical
  lines: backend 7,521 -> 7,481 and frontend 3,508 -> 3,469. Collected cases change from 500 to 498
  backend and 88 to 87 frontend (30 Node and 57 component). The focused composition/lifecycle/CLI/
  publication/profile run passed 97 tests; full backend and frontend suites passed. Removed
  assertions covered private selection and lifecycle call structure, not public behavior, safety,
  concurrency/bounds, real regressions or useful domain examples.
- **Verification:** Full `uv run pytest -q` passed 498 tests with the existing Starlette/httpx
  warning. Frontend `pnpm test` passed 30 Node and 57 component tests; `pnpm lint`, `pnpm typecheck`
  and `pnpm build` passed with 2,966 transformed modules. `uv run ruff check .`, `uv run mypy
  coordinator/src/e87canbus` (61 files), both generated checks, `bash -n scripts/*.sh` and
  `git diff --check` passed. Dead-symbol searches find no active selection mirror, generic builder,
  React provider, reference-counted transport owner or test-only teardown symbol; roadmap/log
  references remain factual. After controlling review, focused CLI/composition/live coverage passed
  28 tests and the full Ruff/mypy/generated/shell/diff set passed again.
- **Browser/physical checks:** Browser setup and discovery returned no available browser, so no new
  interactive `/dev` and `/car` light/dark 800x480 or same-document cycle evidence is claimed.
  Existing route/component acceptance and singleton transport tests passed, and changed layout/
  visual code is limited to removing the non-rendering provider. Real CAN TX and physical steering
  were unavailable and were not enabled or claimed.
- **Dependencies/migrations:** None. No dependency, lockfile, SQLite schema, CAN protocol, firmware,
  generated contract or tracked database artifact changed; the test-modified SQLite artifact was
  restored.
- **Compatibility/removal:** None. All in-repository callers moved in this phase. There is no alias,
  facade, forwarding constructor, deprecated import or parallel transport; therefore there is no
  consumer, removal condition or expected later phase.
- **Target variance:** The phase exceeds its 200-line minimum with 202 net production lines removed.
  Tests and documentation do not inflate the claim; listener setup retained in `transport.ts` is not
  counted as reduction merely because it moved within the file. Cumulative production reduction is
  921 lines from the roadmap base.
- **Remaining:** None for Phase 5. Fresh browser matrix evidence remains unavailable rather than
  inferred; no behavior or safety boundary was weakened to compensate.
- **Next handoff:** Phase 6 may reduce tests tied to deleted internals, while retaining explicit
  constructor safety, controller/lifecycle ownership, singleton transport/reconnect behavior,
  bounded trace/publication and meaningful route/domain/integration evidence.

### 2026-07-15 — Phase 4: publication diagnostics reduced to operator decisions

- **Status:** Verified
- **Scope:** Reduced Socket.IO publisher/service/public/frontend diagnostic copies while leaving
  fixed events, envelopes, complete reconnect snapshots, topic-local revisions, resource
  invalidation, frontend transport ownership, publisher scheduling and every retention boundary
  unchanged.
- **Deletion hypothesis:** `PublicationDiagnostics` copied the publisher's own state into
  `PublisherDiagnostics`; event/connection/subscriber/maxima counters and repeated availability,
  effect-count and fault-summary trees had no UI, policy or current operator-decision consumer.
  `ControllerAdapterSnapshot.effects` and simulated process effect history existed only to feed
  those public counters. Current device/network availability already belonged to `devices.state`.
- **Production accounting:** Phase base
  `22205575c573e5163275c01e69337c40f188fb5a`. Backend production is +24/-273, net -249 across five
  touched files: `api/internal/live.py` +10/-103, `api/models/live.py` +7/-129, `live.py` +0/-1,
  `service.py` +7/-38 and `simulation/runtime.py` +0/-12. Frontend production is +6/-74, net -68
  across three files: `api/live-events.ts` +2/-38, `live/live-store.ts` +2/-18 and
  `live/test-fixtures.ts` +2/-18. The latter is functionally a test fixture but is counted as
  production to match Phase 1's `frontend/src` predicate. Total production is +30/-357, net -327;
  0 files were added/deleted and 8 were touched. Tests are +24/-40, net -16 across two backend
  files; generated schema is +12/-244, net -232; documentation is +128/-23, net +105 across this
  log and `docs/reliability.md`; temporary compatibility +0/-0. Cumulatively from roadmap base
  `a31d2f8`, production is +306/-1,025, net -719: backend +296/-929, net -633, and frontend
  +10/-96, net -86. Current production is 8,017 backend lines/61 files and 9,084 frontend lines/134
  files. The largest
  surviving additions are +10 in `api/internal/live.py` for the two explicit drop counters and
  direct canonical `PublisherDiagnostics` construction, +7 in `api/models/live.py` for their strict
  public validation and +7 in `service.py` for the reduced canonical records/current-warning
  policy. They directly replace larger generic maps and copied trees; no later deletion is needed
  to justify them.
- **Cognitive accounting:** Operational/publication/lifecycle owners remain 1/1, 1/1 and 1/1;
  bounded queues/stores remain one service inbox, one latest-topic map, one resource deque, one
  trace deque and one Engine.IO queue per peer. Removed named concepts: `PublicationDiagnostics`,
  `FaultSummaryState`, the adapter effect-diagnostic projection, simulated `_effect_history`, the
  publisher connected-socket set, three generic per-event counter maps, two publisher historical
  maxima, three inbox historical public fields and the duplicated health availability/effect-count/
  latest-fault groups. Added concepts: 0; two named monotonic drop facts replace a generic event
  counter map. Publisher health representations change from publisher -> service -> public to
  direct service -> public (end-to-end contract copies 4 -> 3 including TypeScript), and publisher
  health propagation loses one conversion hop (4 -> 3). State owners, scheduling mechanisms,
  schemas, topics and queues added/removed: 0/0.
- **Changed:** The publisher now constructs the service-owned immutable diagnostic record directly.
  Public health retains ready/fatal truth; explicit network/device/steering faults; inbox depth,
  capacity, current latency, warning and overflow; persistence availability/fault; and publisher
  running, failure, trace/resource drop, slow-peer-isolation and fault facts. Availability and
  selected capability state are read from canonical `devices.state`, not copied into health.
  Disconnect synchronizes Engine.IO saturation evidence but ordinary connection/subscription
  changes no longer advance health revisions. Queue-latency logging triggers on warning entry
  instead of retaining projected maxima/counters.
- **Protected behavior:** Complete connect/resync snapshots and new-boot replacement remain; topic
  payloads and revisions remain complete and latest-value coalesced; controller notification never
  awaits socket delivery; resource and trace retention remain fixed at 8 and 2,000; trace remains
  opt-in, batched and reset on session identity; each peer queue remains finite and aborts the slow
  peer; publisher failure health remains non-recursive; readiness, fatal and overflow truth remain
  honest; frontend listeners remain singleton-owned and unchanged.
- **Tests:** Retained public snapshot/boot/topic/resource and generated-schema contracts; readiness,
  fatal, overflow and no-TX safety; stalled-emitter, peer-capacity, trace opt-in/session, shutdown
  deadline and non-recursion bounds; simulator/API integration; and frontend boot/revision,
  singleton-listener, resubscription and bounded-trace regressions. Removed assertions for active
  socket count, trace capacity and duplicate latest-fatal summaries with those fields. Expanded
  boundary tests prove the 2,000-row trace ring and eight-change resource deque drop oldest values.
- **Test accounting:** Tracked tests remain 56 files and change from 11,045 to 11,029 physical
  lines; backend tests change from 7,537 to 7,521 lines. Collected cases remain 500 backend plus 30
  Node and 58 component cases. The final full backend run passed in 9.89 seconds; frontend unit tests
  passed in 0.19 seconds and components in 3.44 seconds. No test file or case was removed; -14 net
  lines remove retired diagnostic assertions while preserving public behavior, safety,
  concurrency/bounds, real regression and integration classifications.
- **Verification:** Focused publication/socket/reliability/contract/simulator/controller/live tests
  passed 81 cases after correcting two new bound-test expectations. Full `uv run pytest -q` passed
  500 tests with the existing Starlette/httpx warning. `uv run ruff check .`, `uv run mypy
  coordinator/src/e87canbus` (61 files), both generated checks, `bash -n scripts/*.sh`, frontend
  `pnpm test`, `pnpm lint`, `pnpm typecheck`, `pnpm build` (2,968 modules) and `git diff --check`
  passed. An initial root-level `pnpm` invocation failed because the manifest is under `frontend`;
  the required commands were rerun there and passed. Installed Engine.IO 4.13.3 was inspected:
  its default queue is unbounded and `AsyncSocket.send` awaits `put`, so the bounded override and
  timeout remain required. Dead-field searches find removed production symbols only in factual
  historical roadmap/log material.
- **Browser/soak/physical checks:** The browser-control runtime reported no available browser, so no
  new DOM, document, heap-after-GC, badge or visual route-cycle evidence is claimed. The unchanged
  singleton transport/route ownership retains the prior verified development/production browser
  baseline. An isolated WebSocket/HTTP exercise processed 300 simulated speed commands at 736.9/s,
  cycled trace subscription five times, emitted six bounded trace batches (maximum 80 rows),
  restarted the backend and received a different boot snapshot; a post-restart command returned
  200. Readiness was true, fatal/latency-warning/overflow false, inbox depth 0/1,024, publisher
  failures/drops/saturations zero, and backend RSS was 62,400 KiB before restart and 61,120 KiB
  after. Real CAN TX and physical steering were unavailable and not enabled or claimed.
- **Dependencies/migrations:** None. No dependency, lockfile, SQLite schema, CAN protocol, firmware
  or tracked database artifact changed. The live JSON schema was regenerated from the reduced
  Pydantic owner.
- **Compatibility/removal:** None. There is no facade, alias, parallel payload or deprecated path;
  therefore there is no compatibility consumer, removal condition or expected later phase.
- **Target variance:** The phase exceeds its 300-line minimum with 327 net production lines removed.
  Tests, documentation, generated schema and the fixture's narrative role do not inflate the claim;
  `live/test-fixtures.ts` remains included only because the baseline predicate classifies it as
  frontend production. Cumulative production reduction is 719 lines from the roadmap base.
- **Remaining:** None for Phase 4. Browser/DOM/heap evidence could not be rerun because no browser
  binding was available, but the changed wire shape, bounds, restart and singleton listener risks
  are covered by generated, integration, load and frontend regression evidence without weakening a
  completion criterion.
- **Next handoff:** Phase 5 may reduce composition and frontend seams but must keep this single
  publisher task/diagnostic owner, exact bounded stores, direct service health handoff and canonical
  `devices.state` availability ownership.

### 2026-07-15 — Phase 3: runtime results and simulation adapter collapsed

- **Status:** Verified
- **Scope:** Shortened the live and simulated adapter-to-service path while leaving the controller
  owner, public HTTP/Socket.IO contracts, publisher diagnostics and composition safety selection
  intact.
- **Deletion hypothesis:** The arbitrary `RuntimeExecution.result`, `ControllerCommandResult` and
  `SimulationResult` rewrapped facts that the service could own at the exact completion point.
  `_SimulatedRuntimeAdapter` converted one private simulator snapshot tree into the already-canonical
  service adapter projection. `_ServiceReaderInbox` converted a boolean sink to `queue.Full`, while
  a second live overflow latch duplicated the service's atomic overflow owner.
- **Production accounting:** Phase base
  `058d6374b7ced306e341a987dd1566e1ffd17789`. Backend production is +241/-543, net -302 across six
  touched files, with 0 files added or deleted: `api/internal/commands.py` +2/-9,
  `api/internal/simulation.py` +2/-15, `composition.py` +15/-251, `live.py` +19/-85,
  `service.py` +18/-29 and `simulation/runtime.py` +185/-154. Directory totals are API internal
  +4/-24, backend root +52/-365 and simulation +185/-154. Frontend production +0/-0. Tests are
  +226/-214, net +12 across seven touched backend files: `test_command_api.py` +2/-2,
  `test_controller_service.py` +0/-2, `test_live.py` +13/-6,
  `test_live_publication.py` +4/-5, `test_runtime_activation.py` +8/-8,
  `test_simulation_runtime.py` +199/-149 and `test_simulator_api.py` +0/-42. Documentation is this
  log +106/-11; generated artifacts +0/-0; temporary compatibility +0/-0. Cumulatively from roadmap
  base `a31d2f8`, production is +280/-672, net -392: backend +276/-650, net -374, and frontend
  +4/-22, net -18. Cumulative documentation is +584/-9. The largest production addition is +185 in
  `simulation/runtime.py`: the existing
  session-counter carry-forward, changed-topic comparison and canonical adapter projection policy
  moved from the deleted 251-line forwarding adapter into its actual simulated-runtime owner. This
  move is not counted alone as reduction; the measurable result is the eliminated intermediate
  snapshot/result models and the cumulative net deletion. No later deletion is required to justify
  a surviving addition.
- **Cognitive accounting:** Operational owners remain 1/1, bounded operational queues 1/1,
  lifecycle owners 1/1 and public schemas 0 added/0 removed. Removed named production concepts:
  `ControllerCommandResult`, `SimulationResult`, `SimulatorSnapshot`, `SimulatedNetworkStatus`,
  `SimulatedSteeringSnapshot`, `_SimulatedRuntimeAdapter`, `ReaderInbox`, `_ServiceReaderInbox`,
  the duplicate live `InboxOverflow`, `SimulationSessionFailed` and two copied factory aliases.
  Added concepts: 0. The common simulated command path changes from `Commit` ->
  `SimulationResult` -> `_SimulatedRuntimeAdapter` -> `RuntimeExecution` ->
  `ControllerCommandResult` -> service revision remap to `Commit` -> one `RuntimeExecution` topic/
  event update -> service-owned matched revision. Simulation projection changes from
  `SimulatorSnapshot` -> adapter field remap -> `ControllerAdapterSnapshot` to direct canonical
  projection. Live reader submission loses the boolean-to-exception adapter and duplicate overflow
  handoff. Private contract copies added/removed: 0/6; flow wrappers/hops added/removed: 0/4;
  queues, schemas and owners added/removed: 0/0.
- **Changed:** Both runtimes return the same reduced update. The service captures the operation's
  revision under its lock before synchronous publisher notification can advance external-health
  revisions, completes successful futures with that exact integer, and rejects the matched future
  when its post-operation controller projection is fatal. The simulated runtime directly supplies
  canonical application, diagnostic and adapter projections and retains process-lifetime CAN
  counters across reset. Live readers call the service sink directly; the service remains the one
  atomic overflow latch. API acknowledgements and error payloads are unchanged.
- **Protected behavior:** One bounded ordered owner and one mutation thread remain; ingress receipt
  timestamps still drive queue latency; overflow remains nonblocking and fatal; commit effects run
  before the operation completes; semantic acknowledgements carry the exact matched service
  revision even when publisher health advances synchronously; fatal work returns 503; reset can
  replace a fatal simulated session; production codecs/transitions/effects remain in the simulated
  path; startup/shutdown/publisher/adapter close order remains deterministic; default live
  composition remains unable to transmit.
- **Tests:** Retained public command/development acknowledgement and error assertions, safety/no-TX
  and grant tests, owner/overflow/latency and blocked-reader concurrency tests, repeated lifecycle
  cleanup, concurrent reset/action, fatal timer/reset recovery, process-counter and production-codec
  domain/integration coverage. Removed two tests that monkeypatched private `SimulationResult`
  values into the API; that private result no longer exists, while real fatal activation and runtime
  paths continue to prove rejection. Tests now assert standalone simulation behavior through the
  canonical application/diagnostic/adapter projections rather than reconstructing the deleted
  simulator snapshot shape.
- **Test accounting:** Backend tests remain 32 files and change from 7,525 to 7,537 physical lines;
  collected cases change from 502 to 500. The +12 lines are direct canonical projection assertions,
  not a mirror model or production seam. Focused owner/runtime/live/simulation/command/lifecycle
  verification passed 145 tests in 6.45 seconds. The full suite passed 500 tests in 10.23 seconds
  with the existing Starlette/httpx deprecation warning. Public behavior, safety, concurrency/
  bounds, real regressions and useful domain examples remain represented.
- **Verification:** Focused 145-test run and full `uv run pytest -q` passed. `uv run ruff check .`,
  `uv run mypy coordinator/src/e87canbus` (61 source files), `uv run python
  scripts/generate_custom_protocol.py --check`, `bash -n scripts/*.sh` and `git diff --check`
  passed. Repeated app construction/shutdown, blocked-reader close, concurrent command/reset,
  queue-overflow, exact command revision, fatal activation and reset recovery regressions are in the
  focused/full runs. Dead-symbol searches find no active production or test reference to the
  removed result, snapshot, forwarding-adapter, reader-adapter or duplicate-overflow concepts;
  historical roadmap/log references remain factual.
- **Browser/soak/physical checks:** Not run; no public wire, frontend, publisher bound or physical
  adapter capability changed. The full integration suites exercise publication and simulated
  lifecycle behavior. Real CAN TX and physical steering remain unavailable and were not enabled or
  claimed.
- **Dependencies/migrations:** None. No package, lockfile, SQLite schema, generated schema, custom
  CAN protocol, firmware or tracked database artifact changed.
- **Compatibility/removal:** None. No alias, facade, forwarding method, deprecated import or
  temporary result/projection path remains; therefore there is no consumer, removal condition or
  later removal phase. All in-repository callers moved in this phase.
- **Target variance:** The minimum is met with 302 net backend production lines removed. Tests,
  documentation and moved policy are excluded from that reduction claim. Cumulative production
  reduction is 392 lines from the roadmap base.
- **Remaining:** None for Phase 3. Publisher/service/public diagnostic copies remain deliberately
  deferred to Phase 4, where their bounds and non-recursive health policy must stay explicit.
- **Next handoff:** Phase 4 should reduce diagnostic representations and forwarding while retaining
  the publisher's bounded latest-topic/resource/trace stores and Engine.IO peer queue; it must not
  recreate a runtime result or adapter projection facade.

### 2026-07-15 — Phase 2: typed boundary values replace copied representations

- **Status:** Verified
- **Scope:** Consolidated live steering types, nested Socket.IO projection adaptation and durable
  settings/profile response serialization. Protocol versioning, payload fields, command handling,
  repository ownership, publisher behavior and all runtime/safety paths were intentionally left
  unchanged.
- **Deletion hypothesis:** FastAPI already serializes the immutable domain settings/profile
  dataclasses at its real wire boundary, so three manually maintained dictionary serializers were
  redundant. Pydantic can validate matching nested dataclass fields directly without reconstructing
  telemetry, curve points, devices and steering observations field by field. The frontend live
  contract already owns the active steering shape, so the durable API module did not need a second
  structural copy.
- **Production accounting:** Phase base
  `b07ae03a38bb13308cf225ab1912cffb1d9dd82a`. Backend production: +35/-107, net -72 across five
  touched files under `coordinator/src/e87canbus/api`: `internal/settings.py` +5/-22,
  `internal/steering.py` +11/-34, `models/live.py` +6/-41, `routes/settings.py` +3/-4 and
  `routes/steering.py` +10/-6 (directory totals: internal +16/-56, models +6/-41, routes
  +13/-10). Frontend production: `frontend/src/api/steering.ts` +4/-22, net -18. Total
  production: +39/-129, net -90; 0 files added or deleted and 6 touched. Tests +0/-0;
  documentation is this log +93/-6 in `docs/unified-controller-reduction`; generated artifacts
  +0/-0; temporary compatibility +0/-0. Cumulatively from roadmap base `a31d2f8`, production is
  the same +39/-129/-90 and documentation is +488/-8 across the Phase 1 baseline and this log. The
  largest additions are typed return annotations/imports in the
  steering routes (+10 lines) and direct typed return shapes in the steering use cases (+11); they
  replace dictionary-shaped boundaries and enable the larger serializer deletion in this phase,
  not a deferred abstraction.
- **Cognitive accounting:** Operational/durable/transport owners remain unchanged. Removed named
  production concepts: `settings_to_dict`, `definition_to_dict`, `profile_to_dict` and the
  independent frontend `SteeringCurvePoint` declaration; the frontend active curve, definition and
  interpolation names remain only as aliases derived from `SteeringState`. Added concepts: 0.
  Settings/profile flows retain the same file hops but lose the domain-to-private-dictionary
  transformation. Live publication retains one Pydantic wire adapter while removing repeated nested
  telemetry, curve-point, device and actuator reconstruction inside it. Queues 0/0, schemas 0/0,
  contract copies added/removed 0/2 (manual backend response dictionaries and the independently
  maintained frontend steering structure).
- **Changed:** Settings and steering-profile use cases now return canonical immutable domain values;
  FastAPI performs the only response serialization. Matching nested domain/service values enter the
  existing Pydantic live models through `model_validate(..., from_attributes=True)`. Frontend
  steering API types derive from `SteeringState`. Explicit mappings remain where names differ or
  policy combines owners, notably public network IDs and controller health summaries.
- **Protected behavior:** Exact settings/profile JSON, strict request rejection, revision conflicts,
  persistence and resource-change events pass unchanged. Socket.IO v1 schema generation, complete
  reconnect snapshots, `boot_id`/revision/topic semantics, bounded publication and visible malformed
  boundary failure remain intact. No controller owner, queue, transport, grant or lifecycle path was
  touched.
- **Tests:** Retained all authoritative public payload/schema, settings/profile/command API, SQLite,
  live publication, reconnect, frontend live-store/transport and Query ownership tests. No test was
  removed or added: there was no serializer-private test to delete, and the existing public payload
  assertions directly prove the useful contract. Safety, bounds, real regressions and domain examples
  remain in the full suite.
- **Test accounting:** Before/after remains 32 backend files, 502 cases and 7,525 physical lines;
  24 frontend files, 88 cases and 3,508 lines. The full backend run passed in 10.28 seconds; frontend
  passed 30 Node tests in 0.26 seconds and 58 Vitest tests in 4.14 seconds. Test value and count are
  unchanged.
- **Verification:** Focused settings/profile/live-contract/live-publication run passed 45 tests.
  Full `uv run pytest -q` passed 502 tests with the existing Starlette/httpx deprecation warning;
  `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus` (61 source files),
  `uv run python scripts/generate_live_contract.py --check`,
  `uv run python scripts/generate_custom_protocol.py --check` and `git diff --check` passed.
  `pnpm test` passed 30 unit and 58 component tests; `pnpm lint`, `pnpm typecheck` and `pnpm build`
  passed with 2,968 transformed modules. Dead-symbol searches find no removed serializer or copied
  frontend active-curve declaration.
- **Browser/soak/physical checks:** Not run; wire payload assertions and frontend consumption tests
  cover this representation-only change. No physical CAN or steering behavior was changed or
  claimed.
- **Dependencies/migrations:** None. No package, lockfile, SQLite schema, live schema, custom CAN
  protocol, firmware or generated artifact changed.
- **Compatibility/removal:** None. No alias, facade, deprecated route, parallel payload or temporary
  path was introduced; therefore no consumer, removal condition or later removal phase applies.
- **Target variance:** Net production reduction is 90 rather than the nominal 200. Further deletion
  in this phase would require removing strict Pydantic request/wire validation, inlining policy-bearing
  API use cases, or pulling Phase 3 result/projection and Phase 4 diagnostic ownership work forward.
  Those moves would weaken a boundary or overlap sequential phases. The measurable contract-copy and
  transformation reduction is retained for review rather than adding speculative machinery or
  cosmetic churn.
- **Remaining:** None after controlling-agent review accepted correctness, accounting and the
  target variance.
- **Next handoff:** After review, Phase 3 can collapse `RuntimeExecution`, command result and adapter
  projection handoffs. Phase 4 remains responsible for publisher/service/public diagnostic copies;
  neither was duplicated or modified here.

### 2026-07-15 — Phase 1: reproducible baseline and deletion ledger

- **Status:** Verified
- **Scope:** Measured the clean current tree at
  `a31d2f8016bb3d6766425ae5fb244a5058fecc63`, mapped all seven required common flows and classified
  candidate reductions. Production code, tests, generated artifacts, deployment and public
  contracts were intentionally unchanged.
- **Deletion hypothesis:** Later phases can collapse repeated `Commit`/`RuntimeExecution`/
  `SimulationResult` handoffs, simulated/service observation snapshots, publisher/service/public
  diagnostics, field-by-field live/resource adapters, handwritten frontend contract copies and
  test-only composition/transport seams. The canonical controller/service owners, bounded queues,
  strict public validation, safety grants and reconnect semantics are retained.
- **Production accounting:** Base and after are identical: backend 61 files/8,650 physical lines;
  frontend 134/9,170. Added 0, deleted 0, net 0; no production file was added, deleted or touched.
  Largest production-code additions: none. Tests remain 56 files/11,033 lines; generated live
  contract 1/1,277; deployment/scripts 8/463; firmware source 3/150. Documentation changes only:
  `phase-1-baseline.md` +323/-0 and this log +77/-7, for `docs/unified-controller-reduction`
  +400/-7 (one added and one touched file) and a documentation after-state of 67 files/9,264
  physical lines. Generated artifacts and temporary compatibility are each 0 files/0 lines. The
  exact tracked-file count command and cumulative `git diff --numstat` method are in
  `phase-1-baseline.md`.
- **Cognitive accounting:** Before/after production is unchanged: one operational owner, one
  operational queue, six state topics, one frontend transport/store path, three publisher stores
  and one bounded Engine.IO queue per peer. Named production concepts, flow hops, queues, schemas
  and contract copies added/removed: 0/0. The approved later target is removal of 6–10 wrapper/
  projection/diagnostic/selection concepts and 1–3 rewrap hops from each touched flow without
  adding an owner, queue or schema platform.
- **Changed:** Added the factual volume/cognitive baseline, owner inventory, seven flow maps,
  consumer-backed deletion ledger, compatibility inventory, target calibration and test
  disposition. Updated this status and handoff only. No abstraction, route, event, model, queue,
  configuration value or production behavior changed.
- **Protected behavior:** Existing tests and source inspection identify the single bounded ordered
  owner, ingress timestamps, production-path simulation, default no-TX live composition, explicit
  rate-limited grants, Socket.IO/HTTP ownership split, complete reconnect snapshot, `boot_id`
  replacement, bounded publication/trace/peer retention, fatal-result rejection, exact durable
  invalidation and honest readiness/shutdown as non-negotiable.
- **Tests:** Retained suites are classified in `phase-1-baseline.md` as public behavior, safety,
  concurrency/bounds, real regressions and useful domain examples. No tests were added, changed,
  removed or consolidated. Later Phase 6 candidates are only tests tied exclusively to wrappers,
  private factories, repeated serializer layers or unreachable retired internals; safety/public
  negative guarantees remain.
- **Test accounting:** Before/after is 32 backend files, 502 collected cases and 7,525 physical
  lines; 24 frontend files, 88 cases and 3,508 physical lines. Backend collection took 0.44 s.
  Frontend verification passed 30 Node cases in 0.21 s and 58 Vitest cases in 3.66 s. No test value
  was removed.
- **Verification:** `uv run pytest --collect-only -q` collected 502 tests with the existing one
  Starlette/httpx deprecation warning. `pnpm test` passed 30 unit and 58 component tests; existing
  Node experimental-module and missing local Fig shell-hook notices were non-failing. Consumer and
  dead-path `rg` searches confirmed the named wrappers remain locally consumed and retired aliases/
  transports occur only in historical documentation or explicit public-absence tests.
  `git status --short` was empty before work; final `git diff --check` and the untracked-document
  equivalent passed, with only the two intended documentation paths present.
- **Browser/soak/physical checks:** Not run; this phase changes documentation only. The prior
  unified-controller final browser/soak evidence remains applicable. Real CAN TX and physical
  steering were not enabled and no physical behavior is claimed.
- **Dependencies/migrations:** None. No dependency, lockfile, generated schema, SQLite schema,
  protocol or firmware change.
- **Compatibility/removal:** None. Raw `/ws`, snapshot/curve-state HTTP reads, response snapshots,
  legacy owner loops and internal aliases were already removed. Current Socket.IO v1 and semantic
  HTTP contracts are current public surfaces, not compatibility paths. No consumer/removal
  condition applies.
- **Target variance:** Phase 1 correctly changes 0 production lines. Candidate-level estimates
  support retaining the 1,000-line cumulative production target: approximately 200–300 lines in
  Phase 2, 350–500 in Phase 3, 300–400 in Phase 4 and 200–300 in Phase 5. These are review budgets,
  and tests/docs/generated churn does not count.
- **Remaining:** None for Phase 1 after final diff verification.
- **Next handoff:** Phase 2 should first remove duplicated contract representations and mapping
  layers while preserving strict public schemas and exact cache/revision behavior. Expected later
  deletions are the Phase 3 runtime/service result and projection wrappers, Phase 4 diagnostic
  copies and Phase 5 test-only composition/frontend lifecycle seams.
