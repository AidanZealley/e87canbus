# Implementation Log — Hardening Pass 02

Append one entry per completed phase. Do not edit earlier phase entries after a later phase begins;
record corrections in the current entry so the migration history remains visible.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Immediate live-safety containment | done | 2026-07-13 |
| 2 — Timestamped, bounded ingress | planned | — |
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
