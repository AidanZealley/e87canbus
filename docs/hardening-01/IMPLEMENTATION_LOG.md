# Implementation log — hardening pass 01

Append one entry per completed phase, newest at the bottom. Keep entries factual and short —
this log is what the next phase's agent reads to learn what the codebase actually looks like now,
including anywhere reality diverged from a phase doc.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Dead code deletion and boundary cleanup | done | 2026-07-13 |
| 2 — Button dispatch table | not started | — |
| 3 — Time axis | not started | — |
| 4 — Transmit safety | not started | — |
| 5 — Simulator and API robustness | not started | — |
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
