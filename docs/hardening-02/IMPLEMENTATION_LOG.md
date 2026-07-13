# Implementation Log — Hardening Pass 02

Append one entry per completed phase. Do not edit earlier phase entries after a later phase begins;
record corrections in the current entry so the migration history remains visible.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Immediate live-safety containment | done | 2026-07-13 |
| 2 — Timestamped, bounded ingress | done | 2026-07-13 |
| 3 — Explicit immutable domain state | done | 2026-07-13 |
| 4 — Pure transitions and controlled effects | done | 2026-07-13 |
| 5 — Single-owner kernel and live cutover | done | 2026-07-13 |
| 6 — Simulator and API cutover | done | 2026-07-13 |
| 7 — Protocol source of truth and cleanup | done | 2026-07-13 |
| 8 — Steering failsafe groundwork | done with simulator-only deviation | 2026-07-13 |

## Entry template

```markdown
## Phase N — <title> (<date>)

**Result:** done | done with deviations | blocked

**What changed:**

- 3–8 factual bullets naming the affected boundaries.

**Deviations from the phase doc:** None, or each deviation and its reason.

**Safety invariants verified:** Name the relevant invariants from `README.md` and the tests that
prove them.

**Complexity delta:** Name deleted paths and consolidations, any new abstraction introduced, and why
that abstraction removes more complexity than it adds. Record any in-scope simplification that was
deliberately not taken and why.

**Discovered along the way:** New constraints or follow-up work. "Nothing" is valid.

**Checks:** pytest count / mypy / ruff / frontend checks where applicable / generator check where
applicable.
```

## Phase 1 — Immediate live-safety containment (2026-07-13)

**Result:** done with deviations

**What changed:**

- Made `default_config()` application-level RX-only on K-CAN, PT-CAN, and F-CAN.
- Added `simulator_config()` as the explicit K-CAN TX grant and made
  `SimulatorController()` use it by default, preserving the production runtime and TX-policy path.
- Normalized `python-can` operation failures to `OSError` inside `SocketCanBus` and removed the
  `python-can` exception dependency from the live composition.
- Added interruptible exponential reader retry backoff capped at one second; a successful receive
  or timeout resets the delay.
- Renamed `min_id_gap_s` to `min_identical_frame_gap_s`, including the drop reason, tests, and
  documentation; alternating payloads on one ID remain governed by the network budget.
- Reconciled the root and coordinator READMEs, deployment and simulation guides, and custom-ID
  registry around application TX disablement, explicit simulator/bench grants, provisional IDs,
  and separate kernel/hardware listen-only defenses.

**Deviations from the phase doc:** `SocketCanBus` also normalizes `can.CanError` while opening and
closing an interface, not only during send and receive. Keeping all `python-can` exception knowledge
inside the adapter removed the live module's dependency on that library and gives callers one
consistent OS-facing error boundary.

**Safety invariants verified:** Safe live defaults are covered by configuration and live-composition
tests that prove all default networks deny TX and startup reaches no bus `send`. Effects retain one
TX-capability exit: an explicit K-CAN grant still passes startup frames through `RateLimitedCanBus`.
Simulation honesty is preserved: the simulator opts into K-CAN TX but continues through the same
runtime, protocol router, application, and rate limiter. Adapter send/receive tests prove
`CanOperationError` is chained behind `OSError`; reader tests prove errors are isolated and retry
delay is capped.

**Complexity delta:** Deleted the unsafe K-CAN grant from the shared default, the misleading
`min_id_gap_s` name and log reason, the live module's `python-can` import/catch path, and inaccurate
listen-only descriptions. One small frozen-config composition function replaces reliance on an
unsafe implicit default. No compatibility property, alias, alternate event path, new manager, or
dynamic registration was retained. The changed production flow remains direct: composition selects
TX capability, the existing runtime authorizes output, and the existing limiter applies policy.
No deliberate in-scope simplification was deferred.

**Discovered along the way:** The full test run reports an existing Starlette deprecation warning
from FastAPI's `TestClient` compatibility import. It is unrelated to Phase 1. No frontend or
generated protocol artifacts changed.

**Checks:** `uv run pytest -q` — 112 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 26 source files; `uv run ruff check coordinator` — all checks passed. Frontend,
generator, and firmware checks were not applicable.

## Phase 2 — Timestamped, bounded ingress (2026-07-13)

**Result:** done

**What changed:**

- Added frozen `ReceivedCanFrame` ingress envelopes and made them the only input accepted by
  `CoordinatorRuntime.process_frame`; `RoutedCanFrame` now exists only at the protocol-routing
  boundary.
- Made live readers stamp frames immediately after `receive()` with an injected monotonic clock,
  and made simulator endpoint draining construct the same envelope with its injected clock.
- Added validated `runtime_inbox_capacity` and `runtime_queue_latency_warning_s` configuration
  defaults; live composition now creates a finite queue and logs dequeue latency without changing
  observation time.
- Replaced blocking reader insertion with `put_nowait`. The first full-queue result is atomically
  latched and logged with its network, stops all readers and the consumer, discards any frame
  dequeued after the stop, and makes `run_live` return non-zero after joining readers and closing
  buses.
- Documented the bounded live-ingress and overflow behavior in the coordinator README.

**Deviations from the phase doc:** None.

**Safety invariants verified:** Observation time is captured at ingress: fake-clock reader,
runtime, and simulator tests prove health and speed sample timestamps retain receive time across
processing delay, while latency logging does not rewrite it. Overload is explicit: configuration
rejects unbounded capacity, and a deterministic capacity-one live composition proves overflow logs
once, stops, cleans up every bus, and returns non-zero. Simulation honesty remains intact because
in-memory endpoints still emit real CAN frames which are drained into the same runtime decode,
application, and TX-policy path. Safe live defaults and the single TX exit remain covered by the
unchanged default and explicit-grant startup tests.

**Complexity delta:** Deleted the bare-`RoutedCanFrame` runtime mutation path, unbounded live queue,
blocking reader `put`, dequeue-time timestamp substitution, and the old suppress-based dequeue
branch. `ReceivedCanFrame` is the single immutable time-owning input shape. The small live-only
`InboxOverflow` class replaces racy per-reader flags by enforcing atomic first-failure ownership and
is the sole added stateful abstraction. No compatibility overload, alternate ingress path, dynamic
registration, or duplicate timestamp field remains. The changed flow is direct: receive → stamp →
non-blocking enqueue → observe latency → process with original timestamp. No deliberate in-scope
simplification was deferred.

**Discovered along the way:** The existing mutable `speed_valid` flag is still reevaluated on the
periodic tick; Phase 3 already owns replacing that duplicated state with validity derived from the
sample timestamp and evaluation time. Phase 2 preserves the correct sample time and does not add a
second validity mechanism. The existing Starlette `TestClient` deprecation warning remains
unrelated. No frontend or generated protocol artifacts changed.

**Checks:** `uv run pytest -q` — 118 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 26 source files; `uv run ruff check coordinator` — all checks passed. Frontend,
generator, and firmware checks were not applicable.

## Phase 3 — Explicit immutable domain state (2026-07-13)

**Result:** done

**What changed:**

- Replaced mutable `RuntimeState` with frozen `ApplicationState`, `NormalSteering`,
  `MaximumAssistance`, and `SpeedSample` values; controller handlers now replace the complete state
  value atomically.
- Made maximum assistance a tagged steering state that wraps the complete previous normal state;
  mode, manual level, active status, and LED commands are derived projections.
- Made vehicle speed and validity projections of one clamped, source-network-aware sample plus the
  last explicit evaluation time. Speed events and ticks supply that time; no domain clock read was
  added, and the timeout boundary remains inclusive.
- Moved mutable CAN receive health out of application state and onto `CoordinatorRuntime`, which is
  the boundary that observes received frames.
- Replaced callback-dictionary button routing with a direct local `match` and consolidated the two
  assistance-button paths.
- Reworked controller coverage into table-driven behavioral cases for every mapped button from
  Auto and Manual, every mapped press during maximum assistance, releases, unknown buttons, level
  bounds, and fresh, boundary-age, stale, and absent speed samples.
- Reconciled the Phase 5 runtime-health plan with the runtime-owned `RuntimeHealth` boundary moved
  into place by this phase.

**Deviations from the phase doc:** None. The explicit speed evaluation timestamp is stored in the
frozen application state so the existing no-argument snapshot API and tick-driven serialized
behavior remain unchanged; validity itself is never stored.

**Safety invariants verified:** Legal steering states are encoded by the `NormalSteering |
MaximumAssistance` union, and frozen-state tests prove replacement rather than field mutation.
Timestamp ownership is preserved by runtime tests proving an old queued speed frame retains its
ingress observation time and becomes stale when evaluated later. Table-driven tests prove speed is
valid through the configured timeout boundary and invalid when stale or never observed. Existing
full-suite live-default, bounded-ingress, same-path simulator, TX-policy, and publication behavior
remains passing.

**Complexity delta:** Deleted `RuntimeState`, its mutation methods, the independently mutable speed
validity and steering projection fields, `_pre_maximum_assistance_state`, its restore helper and
assertion, four callback registrations, and separate up/down handlers. The small frozen tagged
values replace contradictory fields and hidden saved state; `RuntimeHealth` moves the existing CAN
health responsibility to its actual owner rather than introducing a second path. Steering
projection and initial normalization remain as focused helpers because each centralizes a repeated
rule. There is no compatibility alias, parallel state representation, dynamic registration, or
deliberately deferred in-scope simplification.

**Discovered along the way:** Preserving the external no-argument snapshot contract requires the
last speed evaluation time to be explicit state until the later kernel phases make evaluation time
part of pure transition inputs. Phase 4 remains responsible for pure transition/effect return
values; none were introduced here. Phase 5 must extend the runtime-health value rather than create
a second health representation. The existing Starlette `TestClient` deprecation warning remains
unrelated. No frontend or generated protocol artifacts changed.

**Checks:** `uv run pytest -q` — 129 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 26 source files; `uv run ruff check coordinator` — all checks passed. Frontend,
generator, and firmware checks were not applicable.

## Phase 4 — Pure transitions and controlled effects (2026-07-13)

**Result:** done

**What changed:**

- Replaced the stateful `ApplicationController` mutation API with a pure `transition(state, event,
  config)` function returning a frozen `Transition` containing the complete next state and ordered
  effects; the runtime now commits that state before executing effects.
- Replaced transport-shaped button and speed events with the closed `ButtonPressed`,
  `SpeedObserved`, and `ControlTimerElapsed` domain event set. Button releases are discarded by the
  decoder instead of becoming permanent no-op events.
- Replaced `ButtonLedCommand` with the verified `SetButtonLed` effect and made the protocol router
  directly decode and encode the closed event/effect set without dynamic decoder or encoder
  registries.
- Split CAN receive, transmit, and unrestricted endpoint protocols. Runtime consumers receive only
  `CanReceiver`; the executor receives only explicitly composed `SafeCanTransmitter` capabilities.
- Added the single `EffectExecutor` output path. Missing transmitter capabilities deny TX, output
  failures are logged after commit without rollback, and live, simulated, and isolated bench
  coordinator output use the same executor and safety policy.
- Replaced `RateLimitedCanBus` and the identical-frame rule with one holistic per-network sliding
  window using an injected clock and plain deque. All IDs and payloads share the budget, and excess
  output is dropped rather than deferred.
- Updated coordinator, simulation, and later-phase documentation to describe pure transitions,
  capability denial, and the bounded-window policy.

**Deviations from the phase doc:** None against the corrected phase document. The first
implementation briefly included a default per-ID allowance of two frames per 50 ms. Review found
that value encoded the temporary two-LED startup implementation into a general safety boundary. It
was removed before phase 5 began, and the phase document was corrected to require only the holistic
network window.

**Safety invariants verified:** Deterministic transition tests use literal frozen inputs and prove
equal inputs return equal results without mutating the original state. Runtime tests prove the
decode → transition → commit → effect order and prove a failed effect does not roll state back.
Default executor and live-composition tests prove absence of a transmitter capability denies every
write, while explicit live, simulator, and bench grants encode the expected LED frames.
Output-policy tests prove alternating payloads on one ID and frames spread across different IDs
share the same network budget, excess output drops, and the window refills deterministically.
Receive-only capability tests prove the runtime consumer needs no `send` method. Existing bounded
ingress, ingress timestamp, same-path simulation, legal-state, and default-live-safety coverage
remains passing. A source audit also verified application and feature modules import no protocol,
runtime, simulation, adapter, FastAPI, threading, or queue types.

**Complexity delta:** Deleted the mutable controller class and all handler mutation methods, the
release event/state branch, the old application event/output unions, router callback dictionaries
and registration method, runtime `tx_networks` and `_send_outputs` gates, the combined `CanBus`
consumer protocol, `RateLimitedCanBus`, identical-frame tracking, and obsolete TX-policy fields.
The corrected implementation also deletes the per-ID timestamp dictionary and its two configuration
fields rather than tuning their arbitrary allowance. The direct bench endpoint write was deleted.
The three small structural capability protocols make receive-only access representable without
wrappers. `SafeCanTransmitter` replaces both the old temporary limiter and runtime TX gate, while
`EffectExecutor` replaces runtime and bench routing/gating/error branches with one final writable
boundary. No compatibility alias, parallel mutation path, dynamic registration, duplicate state
field, or deliberately deferred in-scope simplification remains.

**Discovered along the way:** Indexed `0x701 [button_index, colour]` messages make synchronization
cost grow with LED count and allow partial device state when a multi-frame update meets a safety
limit. That protocol migration is deliberately deferred out of hardening-02 and specified in
[`docs/hardening-03/README.md`](../hardening-03/README.md): one validated 16-colour domain value,
one effect, and one packed DLC-8 snapshot frame. Physical NeoTrellis rendering remains separately
gated on verified hardware topology and electrical limits. The existing Starlette `TestClient`
deprecation warning remains unrelated. No frontend or generated protocol artifacts changed.

**Checks:** `uv run pytest -q` — 125 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 28 source files; `uv run ruff check coordinator` — all checks passed. Frontend,
generator, and firmware checks were not applicable.

## Phase 5 — Single-owner kernel and live cutover (2026-07-13)

**Result:** done

**What changed:**

- Replaced `CoordinatorRuntime` with `CoordinatorKernel`; its closed `dispatch` input union is now
  the only application-state and runtime-health mutation path, and it owns the immutable current
  state, lifecycle, health, and monotonically increasing application revision.
- Added frozen `Commit` and diagnostic values. Startup creates revision 1, every decoded domain
  transition increments the revision even when its public snapshot is unchanged, and unknown or
  malformed CAN traffic creates no application commit.
- Moved effect execution outside the kernel. The live main thread now dispatches a commit before
  executing its effects, and executor I/O errors become `EffectExecutionFailed` on the next loop
  turn without rollback or recursive kernel entry.
- Extended immutable per-network runtime health with receive timestamps and reader, effect, or
  inbox-overflow fault status; faults remain diagnostic state rather than application decision
  state.
- Made repeated reader errors fatal after three consecutive normalized failures. Readers emit a
  timestamped `CanReaderFailed` and exit; a successful receive or timeout resets the consecutive
  count. Overflow that cannot fit in the bounded inbox is atomically retained as an
  `InboxOverflowed` input.
- Kept live readers limited to receive, ingress timestamp, and non-blocking enqueue. The calling
  thread alone dispatches startup, frames, timers, faults, and shutdown, retains drift-resistant
  tick scheduling, and returns non-zero for reader, effect, or overflow failure.
- Replaced the simulator's removed runtime methods with a small composition-local adapter that
  drains real in-memory CAN endpoints into `dispatch`, executes returned effects through the same
  TX policy, and explicitly shuts down the old kernel on reset. Browser publication and revision
  consumption remain unchanged for Phase 6.
- Updated coordinator and simulation documentation for the single-owner kernel and fatal fault
  behavior.

**Deviations from the phase doc:** None. The simulator adapter is the temporary Phase 5 bridge
explicitly required before the Phase 6 publication cutover; it does not inject domain events or
mutate kernel state outside `dispatch`.

**Safety invariants verified:** One state owner and deterministic transitions are covered by mixed
startup/frame/timer tests proving stable revisions, snapshots, and effects. Observation-time tests
prove queue latency and delayed processing never replace ingress timestamps. Effect tests prove
commit precedes execution, failures return as later fault inputs without re-entry, and only the
coordinator thread calls `dispatch`. Overload and fault tests prove bounded non-blocking ingress,
visible per-network overflow/reader/effect status, clean bounded thread shutdown, and non-zero live
results. Scheduling tests prove large jumps produce one resynchronized tick and sustained unknown
traffic cannot starve timers. Existing live-default and simulator tests prove absent capabilities
still deny TX and simulated external frames retain the production decode, transition, commit,
effect, and TX-policy path. A source audit found no threading or queue imports in application,
feature, or kernel modules.

**Complexity delta:** Deleted `CoordinatorRuntime`, its four mutation methods (`start`,
`process_frame`, `tick`, and `drain_pending`), its receiver map, ambient clock, executor ownership,
mutable health dictionary, and every compatibility caller. The live loop now has one dispatch path
instead of separate startup/frame/timer calls, and the simulator's direct endpoint drain is only a
temporary input adapter around that same path. `Commit`, the closed frozen input values, and frozen
runtime-health values add production structure required to encode ordering, ownership, revisions,
and fatal status; they replace duplicated mutation entry points and swallowed failures rather than
layering beside them. `EffectFailure` is the minimal executor-to-composition value that makes I/O
failure observable. Duplicate fault branches and an unnecessary simulator pending-fault list were
removed during the simplification audit. There is no compatibility alias, dynamic registration,
callback chain, parallel event pipeline, or deliberately deferred in-scope simplification.

**Discovered along the way:** Three consecutive receive errors provide a bounded fatal-reader rule
while preserving recovery from a transient error; the successful receive/timeout reset prevents
non-consecutive faults from accumulating. Phase 6 still owns commit-driven browser publication and
API revision exposure. The existing Starlette `TestClient` deprecation warning remains unrelated.
No frontend or generated protocol artifacts changed.

**Checks:** `uv run pytest -q` — 129 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 28 source files; `uv run ruff check coordinator` — all checks passed. Frontend,
generator, and firmware checks were not applicable.

## Phase 6 — Simulator and API cutover (2026-07-13)

**Result:** done

**What changed:**

- Replaced the temporary `SimulatorController` and its separate press, release, step, reset, and
  tick mutation methods with one `SimulationEngine.execute` command path over frozen simulation
  command values. The existing bounded quiescence loop, real simulated-device frames, kernel
  dispatch, effect executor, and TX policy remain the operation path.
- Added a bounded simulation command queue and one FastAPI lifespan owner task. REST mutations and
  the periodic control timer enqueue commands; the owner executes each operation and completes its
  ordered WebSocket publication before resolving the submitting request. Saturation returns HTTP
  503, while an unchanged timer emits no snapshot.
- Added kernel revision and monotonic simulation session ID fields to REST and WebSocket snapshots.
  Reset starts a new session and trace sequence at one; every incremental frame now carries its
  session ID.
- Serialized initial WebSocket snapshots with operation publication. A failed socket is logged and
  removed without interrupting delivery to healthy clients.
- Made frontend reduction reject older same-session snapshots and old-session frames, replace state
  on a newer session, and sort/deduplicate trace rows by `(session_id, sequence)`.
- Updated current architecture and simulation documentation for command ownership, backpressure,
  revisioned snapshots, trace sessions, and timer publication behavior.

**Deviations from the phase doc:** None.

**Safety invariants verified:** One state owner and publication-after-commit order are covered by
concurrent API command and reset tests that prove operations and their events remain contiguous and
session ordered. Same-path simulation tests prove browser commands can only operate simulated
devices, reject domain events and application state, and retain receive timestamp, router,
transition, commit, effect, and TX-policy behavior. Revision/session tests prove reset-local frame
identity and frontend rejection of stale or duplicated inputs. Bounded command-queue coverage proves
overflow returns 503 without wedging the owner. Existing live-default, bounded CAN ingress,
capability denial, network TX budget, and external-device unrestricted-output tests remain passing.

**Complexity delta:** Deleted `SimulatorController`, its five public mutation methods, `last_events`,
the unused `_button_pressed` dictionary, the API-wide mutation lock, dynamic method lookup, the
task-local timer baseline, and the parallel LED-update WebSocket/frontend reducer path. Renamed the
module around its actual engine responsibility. The frozen command/result values and one queued
command envelope add the structure required for bounded serialization and request results; the
single engine class replaces the temporary adapter rather than wrapping it. The WebSocket
publication lock enforces initial-snapshot/broadcast ordering and isolates connection membership; it
does not guard engine mutation. Snapshot emission uses one optional trace mode instead of
independent flags, so the invalid combination of a trace-bearing non-publication is not
representable. No compatibility alias, old controller module, alternate event pipeline, dynamic
registration, or deliberately deferred in-scope simplification remains.

**Discovered along the way:** Kernel revision can advance on an unchanged timer without a browser
publication; the next changed snapshot carries the newer committed revision, while GET observes the
latest immutable snapshot. WebSocket sends remain sequential and have no configured timeout, so a
connected peer that neither completes nor fails a send can delay the owner until the bounded command
queue returns 503; choosing a disconnect timeout is deferred because Phase 6 specifies failed-peer
isolation but no latency threshold. The existing Starlette `TestClient` deprecation warning remains
unrelated. No generated protocol or firmware artifacts changed.

**Checks:** `uv run pytest -q` — 133 passed, 1 existing deprecation warning; `uv run mypy` — success,
no issues in 28 source files; `uv run ruff check coordinator` — all checks passed; frontend
`pnpm typecheck` — passed, `pnpm lint` — passed, `pnpm test` — 6 passed. Generator and firmware
checks were not applicable.

## Phase 7 — Protocol source of truth and migration cleanup (2026-07-13)

**Result:** done

**What changed:**

- Added `protocol/custom.toml` as the sole definition of provisional custom CAN IDs, payload
  lengths, byte positions, button states, and LED colours. A standard-library generator now owns
  the Python constants module, button-pad header, and a marked section of the Markdown registry.
- Made the codecs and `CustomCanIds` consume generated values, including generated lengths and byte
  positions, and replaced the partial header-regex drift test with direct parser/renderer tests that
  detect an independent change to any generated artifact.
- Added standard-library AST architecture guards for domain imports, wire-codec imports, simulation
  command construction, default live TX denial, and removed pre-kernel names. Added a CI workflow
  that runs the generator check and all backend/frontend gates.
- Replaced the application timer event at live/simulation ingress with a frozen runtime
  `TimerElapsed` input; the kernel alone translates it to the domain event. Browser simulation
  commands therefore cannot construct application events.
- Deleted the per-network latest-receive health timestamp and its write path because no production
  status or safety decision consumed it. Fault health remains immutable and is consumed by the live
  runner to fail closed.
- Reconciled the root, coordinator, protocol, setup, deployment, and project-context documentation
  around the current kernel flow, generated protocol, bench-only systemd unit, live TX defaults,
  same-path simulation, and Phase 8 evidence gates.

**Deviations from the phase doc:** None.

**Safety invariants verified:** Generated-artifact tests and `--check` cover IDs, lengths, byte
positions, button values, and colour values without rewriting surrounding Markdown prose. Import
guards prove application/features do not import protocol/runtime/simulation/adapters/FastAPI/thread
or queue boundaries, wire codecs do not import application types, and simulation commands cannot
construct domain events. The default-composition guard proves every live network still denies TX.
Existing full-suite tests continue to prove ingress timestamp ownership, bounded queues, immutable
single-owner commits, commit-before-effect ordering, capability and network-window enforcement,
fault fail-closed behavior, and the production-equivalent simulated CAN path.

**Complexity delta:** Deleted the manually duplicated Python wire constants, the partial firmware
regex drift test, all test imports of obsolete wire aliases, the unused latest-RX health field and
its replacement helper, and the direct live/simulation dependency on the application timer event.
The two frozen generator schema values validate the only source file and feed three plain render
functions; they replace three manually synchronized artifacts rather than adding another protocol
representation. `TimerElapsed` replaces a layer-crossing input with one explicit runtime value and
one visible kernel conversion. There is one protocol generation path, one timer ingress path, one
kernel mutation path, and one effect exit; no compatibility alias, temporary adapter, dynamic
registration, unused runtime field, or deliberate in-scope exception remains.

**Discovered along the way:** The repository had no CI workflow, so Phase 7 added the first one
rather than assuming an external job would run `--check`. The current systemd unit and bootstrap
script intentionally remain the isolated `can0` bench ping-pong deployment; the three-network live
runner remains manual and RX-only by default. No frontend source or actuator firmware changed.

**Checks:** `uv run pytest -q` — 143 passed, 1 existing Starlette deprecation warning;
`uv run mypy` — success, no issues in 29 source files; `uv run ruff check coordinator` — all checks
passed; `uv run python scripts/generate_custom_protocol.py --check` — passed; frontend
`pnpm typecheck` — passed, `pnpm lint` — passed, `pnpm test` — 6 passed. Additional
`uv run ruff check scripts/generate_custom_protocol.py` and `bash -n scripts/*.sh` checks passed.
The button-pad `pio run` build passed after its byte-position constant adopted the generated
`BUTTON_INDEX` name. Phase 8 actuator firmware checks were not applicable.

## Phase 8 — Steering failsafe groundwork (2026-07-13)

**Result:** done with deviations

**What changed:**

- Replaced the speculative 200–800 mA configuration and conversion helpers with a validated
  dimensionless `0.0..1.0` assistance curve and effect. Auto, Manual, and Maximum now select their
  bounded targets in the pure control-timer transition.
- Added explicit zero-assistance reasons for never-seen/stale speed, runtime fault, and shutdown.
  Startup, reader failure, inbox overflow, and shutdown commits all carry the command through the
  existing commit-before-effect path.
- Extended the effect executor with one optional steering-actuator capability. Live composition
  supplies none; it has no actuator adapter, simulated decoder, current value, wire command, CAN
  grant, or other path to steering actuation.
- Added a simulation-only extended speed frame and router, used only by `SimulationEngine`. The API
  operates a simulated external vehicle node, which emits the encoded frame on in-memory F-CAN and
  reaches the ordinary ingress timestamp, decode, transition, commit, and effect path.
- Replaced the passive K-CAN steering placeholder with a direct simulated actuator that records
  dimensionless commands and derives zero assistance after a 250 ms fake-clock watchdog timeout.
  Simulator snapshots expose its assistance, last command reason, and timeout status.
- Made speed evaluation time monotonic. A delayed old frame processed after a later timer can no
  longer move evaluation time backward and briefly clear the stale-speed fallback.
- Updated the root, coordinator, simulation, hardening overview, and phase documents to distinguish
  simulator groundwork from verified electrical safety and to retain every road-use gate.

**Deviations from the phase doc:** The user explicitly accepted a simulator-only scope because
verified BMW speed captures, actuator protocol/hardware, safe current data, and definitive vehicle
IDs cannot currently be obtained. Consequently this phase does not implement a verified BMW
decoder, current command, physical actuator adapter, independent hardware watchdog, malformed
verified-traffic threshold, collision validation, deployment grant, road test, or actuator firmware.
The synthetic extended speed message is isolated to the simulation package and is not a candidate
BMW definition. Zero assistance is only the simulated controller's fallback; it is not claimed as
an electrically safe target. The full verified acceptance criteria remain road-use gates.

**Safety invariants verified:** Same-path simulation tests prove speed changes originate at the
simulated vehicle as encoded CAN and traverse ingress timestamping, the kernel decoder, pure
transition, ordered commit, executor, and actuator capability. Late-frame tests prove observation
time governs freshness and cannot regress behind a later timer. Deterministic transition tests
cover never-seen and stale Auto, fresh interpolation, recovery on the next timer, and bounded Manual
and Maximum targets without speed. Live-loop tests prove reader failure and inbox overflow command
the fallback before shutdown, while watchdog tests prove command silence independently derives zero
simulated assistance without sleeps. Architecture and live-composition tests prove the synthetic
router and actuator capability are absent live, all default CAN networks remain TX-disabled, and no
placeholder BMW ID became executable. The kernel remains the sole application-state owner and the
executor remains the sole effect exit.

**Complexity delta:** Deleted the unverified milliamp bounds, current interpolation/conversion API,
passive `SimulatedSteeringControllerNode`, its K-CAN endpoint, generic 32-pass cascade loop, reactive
placeholder tests, and stale documentation. `SetSteeringAssistance` replaces disconnected steering
math with one validated effect. The small actuator capability isolates the still-unknown hardware
boundary, while `SimulationProtocolRouter` enforces that synthetic decoding cannot enter live
composition. `SimulatedVehicleNode` and `SimulatedSteeringController` replace passive placeholders
with the two stateful external actors required by the scenarios. There is one target-selection path,
one executor path, one synthetic decoder, and one simulated actuator owner; no compatibility alias,
parallel event pipeline, callback registry, or deliberate in-scope simplification remains.

**Discovered along the way:** The previous `SpeedObserved` transition reset `speed_evaluated_at` to
the frame's observation time. If an old queued frame arrived after a later timer, that could make the
old sample temporarily appear fresh. The transition now preserves the maximum evaluation time. The
existing Starlette `TestClient` deprecation warning remains unrelated. Real safe-current selection,
electrical fallback behavior, verified speed decoding, hardware watchdog behavior, malformed-frame
policy, and deployment/physical recovery procedures remain deferred until evidence exists.

**Checks:** `uv run pytest -q` — 168 passed, 1 existing Starlette deprecation warning;
`uv run mypy` — success, no issues in 30 source files; `uv run ruff check coordinator` — all checks
passed; `uv run python scripts/generate_custom_protocol.py --check` — passed; frontend
`pnpm typecheck` — passed, `pnpm lint` — passed, `pnpm test` — 6 passed; `git diff --check` — passed.
No generated protocol artifact or firmware changed, so generation and actuator-firmware build steps
were not applicable beyond the generator drift check.
