# Architecture decisions

These records capture architectural choices that still govern the repository. Hardening plans and
implementation logs are temporary working material; accepted decisions live here after the work is
complete.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-single-owner-event-kernel.md) | Single-owner event kernel | Accepted |
| [0002](0002-capability-controlled-output.md) | Capability-controlled, bounded output | Accepted |
| [0003](0003-production-path-simulation.md) | Production-path simulation with one owner | Accepted |
| [0004](0004-generated-custom-protocol.md) | Generated custom-protocol source of truth | Accepted |
| [0005](0005-atomic-button-led-snapshots.md) | Atomic button-pad LED snapshots | Accepted |
| [0006](0006-evidence-gated-hardware-behavior.md) | Evidence-gated hardware behavior | Accepted |

New records should be numbered sequentially and contain `Status`, `Context`, `Decision`, and
`Consequences` sections. Supersede an accepted record with a new ADR instead of rewriting the old
decision.
