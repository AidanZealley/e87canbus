# Simplified coordinator implementation plan

Status: in progress.

## Orchestration record

- Integration branch: `feature/simplified-coordinator`
- Starting commit: `d2c00ed5313954142ff8205da5adab4da5882f48`
- Reviewers: fresh lead subagents inheriting the orchestrator's model and effort
- Specification approved at commit: `d2c00ed5313954142ff8205da5adab4da5882f48`
- Started: `2026-09-23`
- Baseline verification: all Workstream 1 targeted commands passed at the starting commit on 2026-09-23 (pytest, OpenAPI check, mypy, ruff, lint-imports, diff check, frontend API check, coordinator-client typecheck, coordinator tests and console tests).

## Workstream order

| # | Workstream | Depends on | Status |
|---:|---|---|---|
| 1 | [Remove the high-beam flash feature](01-remove-high-beam-flash.md) | Approved Slice 1.5 | Accepted |
| 2 | [Retire button-pad CAN and coordinator feedback](02-retire-button-pad-can.md) | Workstream 1 | Accepted |
| 3 | [Retire Servotronic and delete the device-CAN platform](03-retire-servotronic-control.md) | Workstream 2 | Accepted |
| 4 | [Reduce the coordinator to its retained responsibilities](04-simplify-coordinator-core.md) | Workstream 3 | Accepted |
| Final | [Whole-feature review](final-review.md) | Workstreams 1-4 | Not started |

Each lead updates its own row on each transition, using one of `Not started`, `Implementing`,
`Review`, `Remediation`, `Closure review`, `Blocked` or `Accepted`. Only one workstream is active at
a time.

## Why these boundaries

Workstream 1 removes one complete product feature and replaces command-specific defaults with one
selected empty profile. Workstream 2 removes the button-pad behavior while Servotronic remains a
real consumer of the shared device-CAN system. Workstream 3 removes Servotronic and the shared
system together. This avoids an intermediate commit containing an empty generated protocol,
registry, ISO-TP stack or effect executor. Workstream 4 audits and simplifies the surviving kernel,
runtime and publication contracts after the old system is gone.

## Cross-workstream contracts

- Button profiles and desired steering state survive. Device availability and applied-device state
  do not.
- A fresh database contains one selected `Default` profile with sixteen unassigned slots. Existing
  prototype databases are replaced, not migrated.
- After Workstream 3, CAN in coordinator application code means vehicle observation. Low-level bus
  objects may still send frames for vehicle simulation, but live composition grants no transmitter.
- The kernel retains only vehicle observations, desired intents, active profiles and curves, and
  complete publication projections.
- Browser SSE remains the only live browser transport. Workstreams regenerate OpenAPI and Hey API
  artifacts whenever their source contracts change.
- No workstream adds the independent device API or its scene document. Slice 02 owns both.

## Ownership handoffs

Workstream 1 owns removal of the high-beam command and command-specific profile defaults. Workstream
2 owns button transport and feedback deletion. Workstream 3 owns desired steering semantics plus
complete deletion of the shared protocol, registry, ISO-TP, firmware, device types and effect
executor. Workstream 4 owns the final kernel, commit, runtime, diagnostics and topic contracts.

Later owners may simplify accepted code but must return lost product state or incomplete deletion to
the workstream that owns that behavior.

`domain/controller/button_leds.py` is deleted with its output type and browser consumer. Slice 02's
first workstream ports its colour and animation resolution from this workflow's starting commit, so
delete it here rather than retaining a function with no consumer.

## Whole-feature acceptance

- High-beam flash, coordinator button feedback and coordinator-side Servotronic execution are gone.
- The custom protocol, registry, ISO-TP, old firmware, project-device simulator peers and generic
  effect executor are gone with their consumers.
- `DeviceRole`, `DeviceSource`, lifecycle, catalogue and project-device deployment types are gone.
- Desired steering state, curves, button profiles, vehicle observations and browser SSE still work.
- A fresh database seeds and selects one empty `Default` button profile. No command-specific default
  assignment remains.
- The kernel and runtimes contain only the responsibilities approved by Slice 1.5.
- Live composition has no CAN transmit authority or unused output framework.
- Generated contracts, tests, configuration, dependencies and documentation agree with the result.

## Escalations

Empty until a lead blocks. One entry per escalation. The lead that resolves one records its lasting
decision in its workstream handoff, and in the decision and drift log when later workstreams depend
on it, then removes the entry.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-18 | Create Slice 1.5 before the independent button-pad slice | The cleanup is large enough to obscure and overload Slice 02 implementation and review | Aidan | All |
| 2026-09-18 | Remove high-beam flash and reintroduce vehicle actuation only from a later verified feature | The current feature has no live actuator and should not keep the effect system alive | Aidan | 1, 3, 4 |
| 2026-09-19 | Replace prototype databases instead of migrating the retired command | No deployed data requires a compatibility path | Aidan | 1 |
| 2026-09-19 | Seed one selected empty `Default` profile | This preserves non-empty catalogue and selection invariants without tying defaults to product commands | Aidan | 1 |
| 2026-09-19 | Delete `DeviceRole` and let Slice 02 introduce its identity type | The current type has no consumer outside the old device system | Aidan | 3 |
| 2026-09-19 | Remove Servotronic and the shared platform in one workstream | The shared platform has no useful state after its final consumer disappears | Aidan | 3 |
| 2026-09-20 | Retain `ButtonPressed` and the kernel press-to-intent dispatch with no producer until Slice 02 | Applying button intents is retained responsibility 2, so the input keeps an approved consumer; deleting it as an orphan would force Slice 02 to reintroduce it | Aidan | 2, 4 |
| 2026-09-18 | Keep low-level CAN send operations but no unused application output abstraction | A later named action can add a direct encoder and bounded transmitter without the old executor | Aidan | 3, 4 |
| 2026-09-18 | No external validation gate | The slice deletes unverified output and all retained behavior is repository-testable | Approved Slice 1.5 boundary | All |
