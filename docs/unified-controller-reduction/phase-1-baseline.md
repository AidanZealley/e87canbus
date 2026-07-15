# Phase 1 verified baseline and deletion map

This records the current-tree baseline at commit
`a31d2f8016bb3d6766425ae5fb244a5058fecc63`. The branch was clean before this document was
created. Counts and candidate estimates are evidence for later phases, not permission to weaken a
public contract, bound or safety rule.

## Reproducible volume baseline

The primary production categories follow the roadmap literally: every tracked Python file below
`coordinator/src/e87canbus`, and every tracked file below `frontend/src` except files whose names
contain `.test.`. Generated artifacts are also reported as a non-additive supplementary view where
they overlap those categories. Physical lines include blank and comment lines.

```text
area                              files   physical lines
backend production                  61            8,650
frontend production                134            9,170
tests                               56           11,033
generated live contract              1            1,277
documentation                       66            8,871
deployment/scripts                   8              463
firmware source                      3              150

supplementary generated artifacts    4              313
```

The generated live contract is `protocol/live-events-v1.schema.json`. The supplementary generated
view comprises `coordinator/src/e87canbus/protocol/generated.py`,
`devices/button-pad/include/can_ids.h`, `frontend/src/routeTree.gen.ts` and the generated-section
carrier `protocol/custom_ids.md`; it is not added to the primary totals. Firmware source comprises
the tracked button-pad source, header and PlatformIO configuration. No build output is tracked.

Run from the repository root:

```sh
count() {
  files=$(eval "$1")
  file_count=$(printf '%s\n' "$files" | sed '/^$/d' | wc -l | tr -d ' ')
  if [ "$file_count" -eq 0 ]; then
    lines=0
  else
    lines=$(printf '%s\n' "$files" | xargs wc -l | tail -1 | awk '{print $1}')
  fi
  printf '%-35s %5s %8s\n' "$2" "$file_count" "$lines"
}

count "git ls-files 'coordinator/src/e87canbus/**/*.py' \
  'coordinator/src/e87canbus/*.py'" "backend production"
count "git ls-files 'frontend/src/**' | grep -Ev '\\.test\\.'" \
  "frontend production"
count "{ git ls-files 'coordinator/tests/**/*.py' 'coordinator/tests/*.py'; \
  git ls-files 'frontend/src/**' | grep -E '\\.test\\.'; } | sort -u" "tests"
count "git ls-files protocol/live-events-v1.schema.json" "generated live contract"
count "{ git ls-files 'docs/**'; git ls-files PROJECT_CONTEXT.md README.md \
  coordinator/README.md frontend/README.md devices/README.md protocol/README.md; } | sort -u" \
  "documentation"
count "git ls-files 'deploy/**' 'scripts/**'" "deployment/scripts"
count "git ls-files 'devices/button-pad/src/**' 'devices/button-pad/include/**' \
  'devices/button-pad/platformio.ini'" "firmware source"
count "git ls-files coordinator/src/e87canbus/protocol/generated.py \
  devices/button-pad/include/can_ids.h frontend/src/routeTree.gen.ts \
  protocol/custom_ids.md" "supplementary generated artifacts"
```

Later phases use `git diff --numstat a31d2f8016bb3d6766425ae5fb244a5058fecc63 --` with the same
path predicates. Binary `-` entries must be reported separately, not converted to line counts.

Test collection at the base found 502 backend cases in 32 tracked test files and 88 frontend cases
in 24 tracked test files (30 Node unit and 58 Vitest component cases). Backend collection took
0.44 seconds. The frontend run passed in 0.21 seconds for Node tests and 3.66 seconds for Vitest.

## Canonical owners and protected contracts

- `CoordinatorKernel.dispatch(ControllerInput)` is the only operational-state mutation owner and
  returns the canonical `Commit` after mutation.
- `ControllerService` owns the sole bounded operational inbox, owner thread, process `boot_id`,
  service revision and current composite projection.
- `LiveControllerRuntime` owns SocketCAN readers and live effect execution;
  `SimulatedControllerRuntime` owns the in-memory topology and uses the same codecs, kernel and
  effect policy.
- `build_controller_service` selects the validated composition. Default live selection has no TX
  grants and no steering actuator.
- Pydantic models in `api/models/live.py` own version 1 Socket.IO validation and generated JSON
  schema. `LiveStatePublisher` owns bounded live publication. HTTP owns semantic commands and
  durable resources.
- `frontend/src/live/transport.ts` owns the singleton browser socket; `live-store.ts` owns current
  live state, `trace-store.ts` owns bounded opt-in trace, and TanStack Query owns durable resources.
- The SQLite settings/profile repositories own atomic revisioned persistence.

The following remain protected: ingress timestamps and ordered mutation; a bounded inbox and
bounded Engine.IO, latest-topic, resource and trace retention; slow-peer isolation; complete
reconnect snapshots; `boot_id` reset and topic-local revision rules; one frontend listener set
through React Strict Mode; exact durable cache replacement and other-client invalidation; fatal
commands never acknowledged as successful; honest readiness and shutdown order; production-path
simulation; rate-limited capability output; deny-by-default live TX; and all hardware evidence
gates. No BMW decode, physical steering behavior or live grant is inferred here.

## Common-flow baseline

The hop count is the number of production files crossed on the normal path. A framework boundary
or a genuine owner is a justified hop; a value that only copies or re-labels another value is a
candidate for removal.

### 1. SocketCAN frame to controller commit/effect

- **Owner/mutation boundary:** the `controller-owner` thread calls
  `CoordinatorKernel.dispatch`; readers only submit.
- **Files and values (7 hops):** `adapters/socketcan.py` (`CanFrame`) -> `live.py`
  (`ReceivedCanFrame`, `_ServiceReaderInbox`) -> `service.py` (`_QueuedWork`) -> `runtime.py`
  (`RoutedCanFrame`, decoded `ApplicationEvent`, `Commit`) -> `protocol/router.py` ->
  `application/controller.py` (`Transition`) -> `output.py` (`ApplicationEffect`, failures).
- **Rewrap/copies:** `_ServiceReaderInbox` translates a boolean sink to `queue.Full`;
  `RuntimeExecution` repeats the commit's topics/count around the result. Adapter projections later
  copy application, diagnostics and device facts into a service snapshot.
- **Concurrency/retention:** one bounded service queue; per-reader thread; `InboxOverflow` lock;
  service state lock; network-wide transmitter window. There is no second operational queue.
- **Evidence:** `test_live.py`, `test_runtime.py`, `test_controller_service.py`,
  `test_can_protocol.py`, `test_application_controller.py` and `test_output.py` protect timing,
  ordering, overflow, decode, commit-before-effect, grants, rate limits and failure fallback.

### 2. Semantic HTTP command to authoritative Socket.IO update

- **Owner/mutation boundary:** HTTP validates intent, but only the controller owner mutates state.
- **Files and values (9 hops):** `api/routes/commands.py` request model ->
  `api/internal/operational_commands.py` (`Set*`/`ActivateSteeringCurve`) ->
  `api/internal/commands.py` -> `service.py` (`Future`, `_QueuedWork`) -> `live.py` or
  `composition.py` (`RuntimeExecution`, `ControllerCommandResult`) -> `runtime.py` (`Commit`) ->
  `api/internal/live.py` (pending topic) -> `api/models/live.py` (`LiveEnvelope`) -> frontend
  `transport.ts`/`live-store.ts` (the browser boundary is two files but one transport/store step).
- **Rewrap/copies:** `Commit` becomes `RuntimeExecution`, then `ControllerCommandResult`; the
  publisher re-projects `ControllerServiceSnapshot` into a field-by-field live model. The command
  acknowledgement is intentionally not authoritative state.
- **Concurrency/retention:** the service inbox, command `Future`, publisher latest-topic map and
  bounded Engine.IO peer queue. No HTTP state cache owns live state.
- **Evidence:** `test_command_api.py`, `test_command_gateway.py`, `test_live_publication.py`,
  `transport.test.ts` and `live-store.test.ts` protect bounded submission, timeout ambiguity,
  failed-result rejection, authoritative publication and boot/revision handling.

### 3. Simulation action to virtual CAN, effect and UI convergence

- **Owner/mutation boundary:** the same service owner executes the selected simulated adapter;
  HTTP never edits application state.
- **Files and values (10 hops):** `api/routes/simulation.py` -> `api/internal/simulation.py` ->
  `service.py` (`_QueuedWork`) -> `composition.py` (`_SimulatedRuntimeAdapter`) ->
  `simulation/runtime.py` (`SimulationCommand`, `SimulationResult`, `SimulatorSnapshot`) ->
  `simulation/devices.py`/`simulation/bus.py` (`CanFrame`, trace entry) -> `runtime.py` (`Commit`) ->
  `output.py` -> `api/internal/live.py` -> frontend transport/store.
- **Rewrap/copies:** `SimulationResult` is converted to `RuntimeExecution`; `SimulatorSnapshot` is
  compared and copied into `ControllerAdapterSnapshot`, then Pydantic live models. Network and
  steering observations have parallel simulated and service snapshot types.
- **Concurrency/retention:** service inbox; bounded in-memory topology trace; publisher bounded
  trace ring/latest topics; bounded peer queue. The simulation has no second mutation thread.
- **Evidence:** `test_simulation_runtime.py`, `test_simulator_api.py`,
  `test_simulation_devices.py`, `test_simulation_bus.py`, `test_live_publication.py` and frontend
  workbench/live-availability tests protect codec traversal, reset identity, device convergence,
  fatal behavior and UI masking.

### 4. Controller commit to one browser topic

- **Owner/mutation boundary:** service records the commit/revision atomically; the publisher owns
  transport retention only.
- **Files and values (6 hops):** `runtime.py` (`Commit`) -> live/simulation adapter
  (`RuntimeExecution`) -> `service.py` (`ControllerServiceSnapshot`, topic revision) ->
  `api/internal/live.py` (latest snapshot per `StateTopic`) -> `api/models/live.py`
  (`LiveEnvelope`) -> frontend `transport.ts`/`live-store.ts`.
- **Rewrap/copies:** topics and commit count are repeated in `RuntimeExecution`; each live payload is
  rebuilt from the composite snapshot. `PublicationDiagnostics` is converted to
  `PublisherDiagnostics` and later to `PublisherHealthState`.
- **Concurrency/retention:** service lock; publisher lock; at most one pending snapshot per topic;
  fixed Engine.IO peer queue. Telemetry and health are rate-bounded.
- **Evidence:** `test_live_contract.py`, `test_live_publication.py`,
  `test_socketio_server.py`, `live-store.test.ts`, `transport.test.ts` and
  `live-render.test.tsx` protect schemas, coalescing, peer bounds, topic isolation and narrow render.

### 5. New/reconnected browser to synchronized Zustand state

- **Owner/mutation boundary:** the server service snapshot is authoritative; the singleton
  transport applies one atomic Zustand replacement.
- **Files and values (4 hops):** `api/internal/socketio_server.py`/`api/internal/live.py` connection
  handler -> `api/models/live.py` (`ControllerSnapshotData` envelope) -> frontend `transport.ts` ->
  `live-store.ts` (`bootId`, `topicRevisions`, slices). `LiveDataProvider.tsx` only acquires/releases
  the singleton owner.
- **Rewrap/copies:** the backend snapshot is copied into a public envelope; frontend separately
  hand-maintains the same TypeScript payload shapes. `createLiveTransportOwner` adds lifecycle
  bookkeeping required by Strict Mode but may contain reducible proxy hops.
- **Concurrency/retention:** Engine.IO peer queue; transport singleton counters; Zustand current
  state only; bounded trace store is cleared on disconnect/boot changes.
- **Evidence:** `transport.test.ts`, `live-store.test.ts`, `live-render.test.tsx` and the Phase 8 soak
  protect snapshot-before-connect, resubscribe, one listener set, boot replacement and bounded trace.

### 6. Settings/profile mutation to SQLite and other-client invalidation

- **Owner/mutation boundary:** the SQLite transaction owns durable revision mutation; Query owns
  the client cache. No runtime/live owner claims the resource.
- **Files and values (8 hops):** API route -> `api/internal/settings.py` or
  `api/internal/steering.py` (request-to-domain mapping) -> SQLite repository (domain value and
  transaction) -> internal field-by-field response dictionary -> route response -> frontend API
  TypeScript shape -> TanStack mutation exact `setQueryData` -> resource event through
  `api/internal/resources.py`/publisher to `durable-query-ownership.ts` invalidation/refetch.
- **Rewrap/copies:** domain values are manually copied to dictionaries, Pydantic/request shapes and
  handwritten frontend types. Settings and steering internal modules duplicate repository error
  wrappers. These copies may protect distinct request/resource contracts and must be assessed
  separately rather than removed wholesale.
- **Concurrency/retention:** short `BEGIN IMMEDIATE` transaction; publisher bounded resource deque;
  Query cache. No SQLite transaction spans a controller wait or publication.
- **Evidence:** settings/profile API and SQLite tests, command activation tests,
  `application-settings-query.test.ts`, `durable-query-ownership.test.ts` and editor component tests
  protect revision conflicts, persistence, exact replacement, invalidation and draft preservation.

### 7. Startup, readiness, fatal failure and shutdown

- **Owner/mutation boundary:** FastAPI lifespan sequences owners; service owns controller failure
  state and safe transition; the process/supervisor owns restart.
- **Files and values (7 hops):** `api/main.py` composition -> `api/internal/lifecycle.py` database
  initialize -> `service.py` owner/runtime start -> live reader or simulated adapter ->
  `api/internal/live.py` publisher start -> service `ready` health -> on failure/shutdown the reverse
  sequence stops acceptance, commits safe state, stops publisher and closes adapters; CLI/systemd
  observes fatal exit.
- **Rewrap/copies:** persistence/publisher health enters service-specific diagnostic records and is
  re-projected through the public health model. These layers are candidates only where the
  non-recursive failure policy remains explicit.
- **Concurrency/retention:** service owner/thread and bounded inbox; reader threads; publisher task,
  wake event and lock; Engine.IO tasks; fixed join/cancellation deadlines; systemd bounded restart.
- **Evidence:** `test_controller_service.py`, `test_reliability.py`, `test_live.py`,
  `test_live_publication.py`, `test_socketio_server.py`, CLI tests and deployment assertions protect
  startup order, readiness honesty, fatal exit, safe shutdown, cleanup and bounded deadlines.

## Candidate deletion ledger

Estimates are physical production lines and intentionally overlap at shared seams only where noted;
later phase accounting must use the actual diff, not sum overlapping estimates blindly.

| Candidate | Consumer/protected behavior | Classification | Estimate | Expected phase |
|---|---|---:|---:|---:|
| `RuntimeExecution` plus live/sim conversions of `Commit`, `SimulationResult` and `ControllerCommandResult` | Service revision/notification, command matched revision and trace deltas; keep those facts but avoid repeated wrappers | Collapse | 140–220 | 3 |
| `_ServiceReaderInbox` boolean-to-`queue.Full` adapter and duplicated overflow handoff | Reader test seam and atomic overflow latch; bounded nonblocking ingress must remain | Inline/collapse | 25–50 | 3 |
| `SimulatorSnapshot` -> `_SimulatedRuntimeAdapter` -> `ControllerAdapterSnapshot`, including paired `SimulatedNetworkStatus`/`ObservedNetworkSnapshot` and steering snapshots | Publisher needs current session/device/network/steering observations; ownership distinction is not evident in the duplicate shapes | Collapse | 140–220 | 3 |
| Separate publisher `PublicationDiagnostics`, service `PublisherDiagnostics`, public `PublisherHealthState` and synchronization copies | Operator-visible bounds/failure counters and non-recursive health publication | Collapse/retain selected fields | 120–200 | 4 |
| Health fields that have no operator decision, safety policy, UI rendering or acceptance assertion | Current health endpoint and workbench; each field requires a consumer search before deletion | Delete/decision required | 100–180 | 4 |
| Field-by-field live projection helpers and Pydantic models that duplicate already validated canonical values | Socket.IO v1 schema is public and must remain strict; direct validation/from-attributes may remove copying, not contract validation | Collapse | 100–180 | 2 |
| Handwritten frontend live types duplicated by the generated JSON/backend contract; steering curve types also repeated in `api/steering.ts` | TypeScript compiler, socket typings and editor API; one generated/derived owner must replace copies without adding a schema framework | Collapse | 100–170 | 2 |
| Settings/profile domain -> dictionary -> response/request/frontend field copies and duplicate repository error wrappers | Public HTTP shapes, optimistic revision conflicts and precise cache replacement | Collapse/inline | 80–150 | 2 |
| `CanAdapterKind`, `CanAdapterSelection`, `CompositionSelection`, selection builders and injectable factories used mainly to construct tests | Deny-by-default TX, one ingress authority and mode validation are safety contracts; retain direct validation, delete test-only configurability | Collapse/inline | 120–220 | 5 |
| Frontend `createLiveTransportOwner` proxy/counter layers and provider forwarding module | Singleton connection, Strict Mode cleanup cancellation, trace ownership and reconnect resubscribe are real regressions | Collapse/retain minimum | 50–100 | 5 |
| One-caller API route/internal helpers and serializers that add no validation, error policy or ownership boundary | FastAPI framework boundary and typed errors remain | Inline | 40–90 | 2/5 |
| Config values with only fixed production defaults | Tests override several timing/capacity values; remove only a value with no deployment/operator consumer and no boundedness-test need | Decision required | 20–60 | 4/5 |
| Tests that instantiate private wrappers/factories, repeat the same assertion at multiple layers or assert impossible retired states | No public/safety value once the corresponding production seam is removed | Delete/consolidate | test-only | 6 |

Candidate review must retain the following evidence while deleting the named internals:

- Result/reader/snapshot collapses retain `test_controller_service.py`, `test_live.py`,
  `test_runtime.py`, `test_simulation_runtime.py` and `test_simulator_api.py` owner, timestamp,
  commit, command-result, reset and failure assertions.
- Diagnostic/health reductions retain `test_live_publication.py`, `test_socketio_server.py` and
  `test_reliability.py` bounds, non-recursion, readiness, fault and shutdown assertions.
- Live/resource contract consolidation retains `test_live_contract.py`, command/settings/profile
  API tests, SQLite tests, `live-store.test.ts`, `transport.test.ts`,
  `application-settings-query.test.ts` and `durable-query-ownership.test.ts` schema, revision,
  reconnect, exact replacement and invalidation assertions.
- Composition/frontend seam reduction retains `test_controller_service.py`, `test_live.py`,
  `test_architecture.py`, `transport.test.ts` and `live-render.test.tsx` no-TX, one-authority,
  Strict Mode singleton, resubscription and narrow-render guarantees.
- Configuration and test-only deletions retain every test that proves a current capacity, deadline,
  freshness limit, rate limit, negative safety boundary or public route absence; only redundant
  private-shape coverage may disappear.

The ledger finds no safe complete deletion of `ControllerService`, `CoordinatorKernel`, the service
inbox, publisher latest-topic map, Engine.IO peer queue, trace ring, SQLite transaction owner,
frontend singleton transport or Zustand live store. They each protect a named ownership, bound or
public behavior.

## Compatibility inventory

None is required by Phase 1. The completed unified-controller cutover already removed raw `/ws`,
`GET /api/snapshot`, `GET /api/steering/curve-state`, response snapshots, legacy owner loops and
internal aliases. Current Socket.IO v1 events, semantic HTTP commands/resources and the canonical
CLI are present contracts rather than compatibility paths. Therefore there is no compatibility
consumer, temporary reason, removal condition or expected removal phase to record.

## Target and cognitive calibration

The candidate-level estimates support retaining the programme target of at least 1,000 net
production lines removed. A realistic non-overlapping range is approximately 1,150–1,450 lines:
200–300 in Phase 2, 350–500 in Phase 3, 300–400 in Phase 4 and 200–300 in Phase 5. These are review
budgets, not acceptance permission. An addition is acceptable only when it enables a named later
deletion or improves a real ownership/validation boundary; cumulative unexplained growth is a
finding. Test, documentation and generated churn never counts toward the target.

At the base there is one operational owner, one operational queue, six state topics, three bounded
publisher retention mechanisms (latest topic, resources and trace), one bounded Engine.IO queue per
peer, and one frontend live transport/store path. Later work should keep those owner/queue counts
flat or lower. The concrete target is to remove 6–10 result/projection/diagnostic/selection concepts,
remove 1–3 rewrap hops from each touched common flow, and reduce independently maintained live and
resource contract copies. No new queue, schema platform, generic framework, facade or owner is
justified by this baseline.

## Test disposition

Retained authoritative groups are:

- **Public behavior:** command/resource API, Socket.IO schema/events, reconnect snapshot,
  boot/revision handling, resource conflicts and exact invalidation.
- **Safety:** no default live TX, explicit grants/rate limits, one device authority, fatal command
  rejection, safe fallback/shutdown and hardware evidence gates.
- **Concurrency/bounds:** inbox overflow/latency, latest-topic coalescing, trace/resource/Engine.IO
  bounds, slow peers, shutdown deadlines and Strict Mode singleton ownership.
- **Real regressions:** snapshot-before-connect, trace resubscription, stale/new-boot handling,
  repeated lifecycle cleanup, disconnected UI masking and the former browser retention failure.
- **Useful domain examples:** steering modes/curve evaluation, telemetry freshness, atomic LED
  snapshots, production codec round trips and SQLite revision behavior.

Tests expected to disappear only with deleted internals include direct construction of private
runtime/result/projection wrappers, duplicate composition-factory matrices that do not add an
authority case, repeated serializer assertions already covered by the public schema, and negative
searches for private names whose retired state is no longer reachable. Negative tests remain when
absence itself protects current safety, ownership, boundedness or a retired public route.

## Phase 1 before/after

Production files/lines, named production concepts, common-flow hops, queues, schemas and public
contract copies are unchanged. Phase 1 adds documentation only; it neither moves nor reformats
production code and introduces no compatibility path.
