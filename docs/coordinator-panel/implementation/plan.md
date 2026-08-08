# Coordinator panel implementation plan

Status: approved; implementation has not started.

## Orchestration record

Complete these fields before starting implementation:

- Integration branch: `feature/coordinator-panel-implementation`
- Starting commit: `6179d6f8d23a1dc5b7c34d3fc5c739c053f255dc`
- Orchestrator: `Codex /root`
- Specification approved at commit: `6179d6f8d23a1dc5b7c34d3fc5c739c053f255dc`
- Started: `2026-08-08`

The implementation branch must begin from the approved specification and mocked frontend card.
Do not begin product work while the specification is still under review unless Aidan explicitly
requests it.

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Shared services](01-shared-services.md) | Approved spec | Accepted | `a17dd72e874ed43f3280f46f9cf91e31717ee64c` |
| 2 | [Simulator integration](02-simulator.md) | 1 | Closure review | — |
| 3 | [Production runtime](03-production-runtime.md) | 1, 2 | Not started | — |
| 4 | [QT Py firmware and upload](04-firmware.md) | 1, protocol accepted in 3 | Not started | — |
| 5 | [Pi provisioning and deployment docs](05-pi-provisioning.md) | 3, 4 | Not started | — |
| — | [Whole-feature review](final-review.md) | 1–5 | Not started | — |

Allowed statuses are `Not started`, `Implementing`, `Review`, `Remediation`, `Closure review`, and
`Accepted`. At most one workstream is active unless the orchestrator records non-overlapping file
ownership and a reason for parallel execution.

## Why these boundaries

1. Shared services establish the product state and thin seams without any framework, OS, serial,
   or frontend concerns.
2. The simulator proves those services through a complete user-visible path before physical I/O is
   introduced.
3. Production runtime adds only the real UART and NetworkManager edges and application lifecycle.
4. Firmware implements the already accepted semantic protocol independently of Pi internals.
5. Provisioning connects the known runtime and firmware requirements to a fresh Pi without making
   runtime code responsible for system configuration.

The sequence intentionally prefers reviewable handoffs over maximum parallelism. Workstream 4 is
technically independent after the UART contract is accepted, but should remain sequential unless
there is a concrete schedule reason to parallelize it.

## Cross-workstream contracts

These contracts are frozen by the specification. Changing one requires orchestration approval and
updates to every affected task packet before work continues.

- `CoordinatorStatus`: `starting`, `ready`, `fault`, `off`.
- `PanelDisplay`: `starting`, `ready`, `hotspot_waiting`, `hotspot_connected`, `fault`, `off`.
- Hotspot states: disabled, starting, waiting, connected, stopping, failed.
- Panel button calls the shared panel service; the panel service asks the shared hotspot service to
  toggle.
- Production UART: `STATUS <display>\n` and `BUTTON\n` at 115,200 baud.
- Production and simulator use the same panel service, hotspot service, and display derivation.
- The coordinator kernel has no panel or hotspot dependency.

## Ownership handoffs

Workstreams run sequentially, but some integration files necessarily pass between owners:

- Workstream 1 owns the new shared modules and their focused tests. Later agents consume them and
  should request owner remediation rather than casually rewriting their rules.
- Workstream 2 first owns simulator API and frontend integration files.
- Workstream 3 may extend application construction and lifecycle files touched by workstream 2 to
  select production adapters. It must preserve the accepted simulator path.
- Workstream 4 owns only `devices/coordinator-panel/`, its upload script, and its device README.
- Workstream 5 owns Pi setup and deployment documentation. It may make a narrowly required runtime
  configuration correction, but substantive runtime changes return to workstream 3's owner.

## Whole-feature acceptance

The branch is ready for final review only when:

- Every workstream record has an accepted closure verdict and commit.
- The worktree is clean.
- All six displays and hotspot button behaviours work through the simulator's shared services.
- Production adapters remain outside the kernel and behind the accepted seams.
- Firmware builds against the final UART contract.
- Setup covers UART, hotspot credentials, permissions, and required packages without exposing the
  password.
- Targeted Python, frontend, firmware, type, lint, and generated-contract checks recorded by the
  workstreams pass.

Physical Pi, UART, LED, hotspot-client, and cancellation validation may remain explicitly pending
until hardware is assembled. Software must not claim those checks passed without evidence.

## Decision and drift log

Add entries only for decisions that affect more than one workstream or change the approved plan.

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| — | None | — | — | — |
