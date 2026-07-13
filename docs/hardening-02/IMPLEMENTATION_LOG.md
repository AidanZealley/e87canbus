# Implementation Log — Hardening Pass 02

Append one entry per completed phase. Do not edit earlier phase entries after a later phase begins;
record corrections in the current entry so the migration history remains visible.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Immediate live-safety containment | done | 2026-07-13 |
| 2 — Timestamped, bounded ingress | done | 2026-07-13 |
| 3 — Explicit immutable domain state | planned | — |
| 4 — Pure transitions and controlled effects | planned | — |
| 5 — Single-owner kernel and live cutover | planned | — |
| 6 — Simulator and API cutover | planned | — |
| 7 — Protocol source of truth and cleanup | planned | — |
| 8 — Verified steering failsafe | blocked on verified evidence | — |

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
