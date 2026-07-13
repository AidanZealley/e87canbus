# Implementation log — hardening pass 01

Append one entry per completed phase, newest at the bottom. Keep entries factual and short —
this log is what the next phase's agent reads to learn what the codebase actually looks like now,
including anywhere reality diverged from a phase doc.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Dead code deletion and boundary cleanup | done | 2026-07-13 |
| 2 — Button dispatch table | done | 2026-07-13 |
| 3 — Time axis | done | 2026-07-13 |
| 4 — Transmit safety | done | 2026-07-13 |
| 5 — Simulator and API robustness | done | 2026-07-13 |
| 6 — Live runner skeleton | not started | — |

## Entry template

```markdown
## Phase N — <title> (<date>)

**Result:** done | done with deviations

**What changed:** 3–8 bullets. Name the files and the shape of the change, not every line.

**Deviations from the phase doc:** "None", or each deviation with one sentence of reasoning.

**Discovered along the way:** anything the phase doc missed that a later phase (or a human)
should know. "Nothing" is a valid answer.

**Checks:** pytest <count> passed / mypy clean / ruff clean (+ frontend typecheck/lint if touched)
```

---

<!-- Entries below. Do not edit previous entries; append only. -->

## Phase 1 — Dead code deletion and boundary cleanup (2026-07-13)

**Result:** done

**What changed:**

- Deleted the unused protocol `SocketCanBus`, speculative feature placeholders, their orphaned
  event/config types, and the obsolete button-mapping tests.
- Removed `strobe_active` from application state and snapshots, simulator serialization, and the
  frontend snapshot type/default.
- Tightened `SpeedUpdateEvent` to identify its source with `CanNetwork` and moved application LED
  encoding into `protocol/router.py`, leaving `protocol/can.py` application-independent.
- Removed simulator compatibility aliases and stopped topology-owned networks from duplicating
  trace storage; added coverage for standalone versus topology-owned trace behavior.
- Added `test_firmware_protocol_sync.py` to guard button-pad CAN IDs, button states, and LED colour
  codes against protocol drift, and updated the coordinator source map.

**Deviations from the phase doc:** None.

**Discovered along the way:** Nothing.

**Checks:** pytest 80 passed / mypy clean / ruff clean / frontend typecheck and lint clean

## Phase 2 — Button dispatch table (2026-07-13)

**Result:** done

**What changed:**

- Replaced button-index conditionals in `application/controller.py` with a typed dispatch table
  built from the existing button constants and bound handler methods.
- Split mode, assistance-down, and assistance-up behavior into small named handlers, with shared
  manual-assistance and maximum-assistance exit helpers preserving the existing behavior.
- Added explicit coverage that an unknown pressed button returns no outputs and leaves the full
  application snapshot unchanged.

**Deviations from the phase doc:** None.

**Discovered along the way:** Nothing.

**Checks:** pytest 81 passed / mypy clean / ruff clean

## Phase 3 — Time axis (2026-07-13)

**Result:** done

**What changed:**

- Added timestamped speed state, speed validity, configured staleness and tick intervals, and the
  application `tick` entry point.
- Updated `CoordinatorRuntime` to reuse one injected clock reading per frame and route tick outputs
  through the existing output sender.
- Threaded injectable clocks through the in-memory CAN topology and simulator controller, and added
  simulator tick processing through the normal pending-frame/event path.
- Added a FastAPI lifespan task that ticks under the simulator lock, broadcasts only application
  state changes, and cancels cleanly during shutdown.
- Exposed `speed_valid` through simulator snapshots and the frontend, which now displays "No speed
  data" while no verified BMW speed decoder exists.
- Added deterministic coverage for tick output routing, fresh/stale/fresh speed transitions,
  simulator clocks and ticks, idle API ticks, and the new configuration defaults.
- Updated `docs/simulation.md` and `coordinator/README.md` for the tick path and absent speed source.

**Deviations from the phase doc:** None.

**Discovered along the way:** Nothing.

**Checks:** pytest 87 passed / mypy clean / ruff clean / frontend typecheck and lint clean

## Phase 4 — Transmit safety (2026-07-13)

**Result:** done with deviations

**What changed:**

- Added deny-by-default per-network TX configuration, with K-CAN as the only default grant, and
  added the configured minimum-gap and rolling network-budget defaults.
- Gated all runtime outputs on explicit TX grants and logged outputs dropped for ungranted
  networks.
- Added `RateLimitedCanBus`, which drops and warns instead of queueing repeated frames or frames
  over the rolling one-second network budget, while passing receives through unchanged.
- Wrapped only TX-enabled simulator Pi buses with the limiter and left simulated external devices
  unrestricted.
- Added deterministic unit coverage for both limits, window refill, receive passthrough, runtime
  grants, and default denial, plus an end-to-end simulator flood test.
- Documented the transmit safety boundary and its configuration in `docs/simulation.md` and
  `coordinator/README.md`.

**Deviations from the phase doc:** The minimum-gap key retains the arbitration ID but only drops a
repeat when its full frame is unchanged; distinct payloads on the same ID are allowed and reset the
gap. A literal per-ID gap dropped the application's two startup LED commands on shared ID `0x701`
and broke the phase's behavior-preservation acceptance criterion, while the network budget still
provides the hard aggregate flood limit.

**Discovered along the way:** The existing LED protocol multiplexes independent button updates on
one arbitration ID, which the phase doc's literal per-ID gap did not account for.

**Checks:** pytest 95 passed / mypy clean / ruff clean

## Phase 5 — Simulator and API robustness (2026-07-13)

**Result:** done

**What changed:**

- Reworked simulator pending-frame processing into a bounded 32-pass quiescence loop that
  accumulates LED updates and warns without raising when a reactive-device cascade does not stop.
- Hardened websocket broadcasts so any per-client send exception disconnects only that client and
  delivery continues to the remaining connections.
- Split simulator serialization into explicit full and slim snapshots: initial loads, websocket
  greetings, and resets include trace data, while commands and tick broadcasts omit it and send
  incremental frame events.
- Added a pure frontend event reducer that preserves trace data across slim snapshots, applies LED
  updates, and sequence-deduplicates a 2,000-entry rolling frame trace.
- Removed the obsolete nullable application-state compatibility path from the workbench and
  steering status component.
- Added deterministic backend coverage for cascades, the pass cap, socket isolation, and 2,000-row
  payload hygiene, plus frontend reducer tests for trace retention, deduplication, capping, and LED
  updates.
- Updated `docs/simulation.md` to describe full reset snapshots and incremental workbench events.

**Deviations from the phase doc:** None.

**Discovered along the way:** Nothing.

**Checks:** pytest 99 passed / mypy clean / ruff clean / frontend typecheck, lint, and 3 reducer
tests clean
