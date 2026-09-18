# Simplified coordinator implementation plan

Status: draft; implementation has not started.

## Orchestration record

- Integration branch: `TBD` (`feature/simplified-coordinator` when started)
- Starting commit: `TBD`
- Orchestrator: `TBD`
- Review command: packet-specific Claude Code command using `--model opus --effort medium --permission-mode plan`
- Specification approved at commit: `TBD`
- Started: `TBD`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Remove the high-beam flash feature](01-remove-high-beam-flash.md) | Approved Slice 1.5 | Not started | — |
| 2 | [Retire button-pad CAN and coordinator feedback](02-retire-button-pad-can.md) | Workstream 1 | Not started | — |
| 3 | [Retire coordinator-side Servotronic control](03-retire-servotronic-control.md) | Workstream 2 | Not started | — |
| 4 | [Delete the project-device CAN platform](04-delete-device-can-platform.md) | Workstream 3 | Not started | — |
| 5 | [Reduce the coordinator to its retained responsibilities](05-simplify-coordinator-core.md) | Workstream 4 | Not started | — |

## Why these boundaries

Workstream 1 removes one complete product feature and its stored-data migration. Workstreams 2 and 3
then remove the two device behaviors separately so their state and frontend consequences receive
focused reviews. Workstream 4 deletes the shared protocol after its final consumers are gone and
removes the now-empty effect executor. Workstream 5 audits and simplifies the surviving kernel,
runtime and publication contracts without mixing that structural pass into protocol deletion.

## Cross-workstream contracts

- Button profiles and desired steering state survive. Device availability and applied-device state
  do not.
- Stored high-beam commands become unassigned slots. No deprecated command spelling remains.
- After Workstream 4, CAN in coordinator application code means vehicle observation. Low-level bus
  objects may still send frames for vehicle simulation, but live composition grants no transmitter.
- The kernel retains only vehicle observations, desired intents, active profiles and curves, and
  complete publication projections.
- Browser SSE remains the only live browser transport. Workstreams regenerate OpenAPI and Hey API
  artifacts whenever their source contracts change.
- No workstream adds the independent device API or its scene document. Slice 02 owns both.

## Ownership handoffs

Workstream 1 owns removal of the high-beam command and its profile migration. Workstream 2 owns
button transport and feedback deletion. Workstream 3 owns desired steering semantics after
Servotronic execution disappears. Workstream 4 owns shared protocol, registry, ISO-TP, firmware and
effect-executor deletion. Workstream 5 owns the final kernel, commit, runtime, diagnostics and topic
contracts.

Later owners may simplify accepted code but must return lost product state or incomplete migrations
to the workstream that owns that behavior.

## Whole-feature acceptance

- High-beam flash, coordinator button feedback and coordinator-side Servotronic execution are gone.
- The custom protocol, registry, ISO-TP, old firmware, project-device simulator peers and generic
  effect executor are gone with their consumers.
- Desired steering state, curves, button profiles, vehicle observations and browser SSE still work.
- Stored high-beam profile slots migrate to unassigned without damaging other bindings.
- The kernel and runtimes contain only the responsibilities approved by Slice 1.5.
- Live composition has no CAN transmit authority or unused output framework.
- Generated contracts, tests, configuration, dependencies and documentation agree with the result.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-18 | Create Slice 1.5 before the independent button-pad slice | The cleanup is large enough to obscure and overload Slice 02 implementation and review | Aidan | All |
| 2026-09-18 | Remove high-beam flash and reintroduce vehicle actuation only from a later verified feature | The current feature has no live actuator and should not keep the effect system alive | Aidan | 1, 4, 5 |
| 2026-09-18 | Clear retired high-beam profile slots to unassigned during migration | This preserves valid bindings without retaining a dead command parser | Aidan and workflow author | 1 |
| 2026-09-18 | Keep low-level CAN send operations but no unused application output abstraction | A later named action can add a direct encoder and bounded transmitter without the old executor | Aidan | 4, 5 |
| 2026-09-18 | No external validation gate | The slice deletes unverified output and all retained behavior is repository-testable | Approved Slice 1.5 boundary | All |
