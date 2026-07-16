# Device registry phase agent prompt

[Overview](README.md) · [Implementation log](implementation-log.md)

Use the prompt below for one implementation phase at a time. Replace
`<PHASE_NUMBER>` with `1`, `2`, `3`, `4`, or `5` before giving it to an agent.

## Phase lookup

| Phase | Document |
|---:|---|
| 1 | [Specification and protocol](phase-1-specification-and-protocol.md) |
| 2 | [Kernel registry and gating](phase-2-kernel-registry-and-gating.md) |
| 3 | [Live contract and `/car` UI](phase-3-live-contract-and-car-ui.md) |
| 4 | [Simulation and `/dev` UI](phase-4-simulation-and-dev-ui.md) |
| 5 | [Button-pad firmware](phase-5-button-pad-firmware.md) |

## Reusable prompt

```text
Implement phase <PHASE_NUMBER> of the device registry and symmetric CAN
handshake.

Before changing anything:

1. Read docs/device-registry-handshake/README.md completely. It is the
   authoritative design and supersedes earlier handshake proposals.
2. Use the phase lookup in
   docs/device-registry-handshake/phase-agent-prompt.md and read the complete
   document for phase <PHASE_NUMBER>.
3. Read docs/device-registry-handshake/implementation-log.md completely. Honor
   prior implementation decisions, recorded deviations, blockers, and current
   phase statuses.
4. Find and read every applicable AGENTS.md for files in scope. In particular,
   frontend/AGENTS.md applies to frontend work.
5. Inspect git status and the current implementation. Preserve unrelated user
   changes and do not assume the repository exactly matches the original plan.
6. Confirm every prerequisite phase is marked Completed. If a prerequisite is
   not complete, do not bypass it; report the concrete dependency conflict.

Implementation rules:

7. Implement only phase <PHASE_NUMBER> plus the smallest compatibility fixes
   necessary to keep the repository coherent. Do not start later-phase product
   work.
8. Follow the overview and phase document's settled names, wire layouts,
   interfaces, timing, lifecycle, and safety boundaries. Do not reopen those
   decisions without a concrete contradiction in the repository; record any
   unavoidable deviation.
9. Simulation must manipulate virtual peer behavior and real encoded CAN
   frames. Never directly force controller registry lifecycle state for a
   product path or UI scenario.
10. Do not weaken live CAN TX grants, collision-validation requirements,
    hardware evidence gates, readiness boundaries, or bench/in-car warnings.
11. Update generated artifacts through their source and generator. Never edit
    generated protocol or schema outputs as independent sources of truth.
12. Preserve the single-owner kernel, canonical buttons.led_colours state, and
    distinction between registry contact, local send success, and physical
    command application.
13. Run every verification command required by the phase document plus
    proportionate regression checks for affected code. Do not hide, skip, or
    reinterpret failures.

Code cleanliness and scope control:

14. Prefer modifying, simplifying, or deleting existing code over adding
    wrappers, mirror models, aliases, generic frameworks, configuration
    options, compatibility layers, or new modules.
15. Add a new type or module only when it creates a real boundary, validation
    guarantee, or ownership distinction that cannot be expressed clearly in
    the existing canonical owner. Do not introduce an abstraction solely to
    make the current change look uniform or to anticipate deferred features.
16. Remove replaced code, models, fields, routes, adapters, fixtures, and tests
    in the same phase unless the phase document explicitly requires temporary
    compatibility. For every retained compatibility path, name its concrete
    consumer and the phase in which it will be removed.
17. Do not preserve obsolete paths merely because updating in-repository
    callers is inconvenient. Update those callers and keep one canonical path.
18. Do not add configuration switches for behavior already fixed by the design
    or for deferred possibilities such as multiple instances, capability
    negotiation, legacy observers, or alternate protocol layouts.
19. Keep tests focused on changed contracts, state transitions, validation
    boundaries, and regressions. Extend existing fixtures/helpers where they
    remain clear; do not add redundant test scaffolding or mirror production
    logic in tests.
20. Before finishing, inspect the complete diff and diff statistics. Perform a
    cleanup pass that removes superseded code, collapses unnecessary layers,
    and confirms the implementation is proportionate to the phase. Record any
    substantial unavoidable increase in structure in the implementation log,
    including which boundary requires it.

Before finishing:

21. Update docs/device-registry-handshake/implementation-log.md in the same
    change. Update the phase status row and append a complete entry containing
    the agent identifier (if available), date, summary, important files,
    public contract/schema changes, exact commands and results, decisions,
    deviations, limitations, follow-up work, and final status.
22. Mark the phase Completed only when all required acceptance tests pass. If
    blocked or required verification cannot run, mark it Blocked and describe
    the blocker and current repository state.
23. Finish with a concise handoff summarizing the implemented outcome, tests,
    remaining risks, and the implementation-log update. Do not claim physical
    readiness from software or simulation results.
```

## Usage notes

- Give an agent only one phase number per run.
- The implementation log is part of each phase's acceptance criteria, not an
  optional retrospective.
- If new user direction intentionally changes the design, update the overview
  and affected phase documents before asking later agents to implement it.
