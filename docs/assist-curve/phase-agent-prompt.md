# Prompt for an agent starting an assistance-curve phase

Copy the prompt below into a new agent session and replace the bracketed values. Give the agent one
phase at a time. If only a slice of a phase is wanted, state the slice and keep all other completion
criteria out of scope.

```text
Work on Phase [N — NAME] of the steering assistance curve roadmap in this repository.

Primary phase document:
docs/assist-curve/[PHASE-DOCUMENT].md

Before changing code, read completely:
- PROJECT_CONTEXT.md
- any AGENTS.md applying to files you may change
- docs/assist-curve/README.md
- the primary phase document above
- docs/assist-curve/implementation-log.md
- docs/decisions/0001-single-owner-event-kernel.md
- docs/decisions/0003-production-path-simulation.md
- docs/decisions/0006-evidence-gated-hardware-behavior.md
- any additional ADR or module README directly relevant to this phase

Implement this phase only. Inspect the current code and tests before designing changes, because the
phase document describes required behavior rather than permission to ignore existing architecture.
If the implementation log or repository has moved beyond the plan, reconcile the difference and
explain it before proceeding.

The key engineering goal is simple, maintainable, well-organized code that a human can follow. Keep
the important behavior obvious and local. Respect the current module boundaries between pure
domain/application logic, runtime ownership, persistence/I/O adapters, API orchestration,
simulation, protocol code and frontend components.

In particular:
- Prefer direct immutable data and small named functions over clever or generic abstractions.
- Do not introduce speculative frameworks, service layers, registries, factories, dependency
  injection machinery or controller-transport code for possible future phases.
- Add an interface only for a real ownership boundary or a materially useful test seam.
- Avoid pass-through wrappers and excessive file fragmentation. Follow existing repository and
  frontend component conventions.
- Keep comments focused on why, invariants, units and failure behavior; do not narrate obvious code.
- Update relevant README/design/API documentation when behavior or responsibilities change.
- Add focused tests alongside the layer that owns each rule, and run verification proportionate to
  the change plus the repository checks affected by it.
- Do not infer BMW messages, physical steering behavior, safe values or live transmit authority.
- Do not implement later phases unless a tiny prerequisite is unavoidable; document any such
  prerequisite explicitly.
- Preserve unrelated user changes in the worktree.

Before implementing, summarize the intended change in a short plan and identify the files/boundaries
you expect to touch. Then implement, test and review the diff for unnecessary abstraction or scope
creep.

At the end:
1. Check every completion criterion in the phase document and state which are satisfied.
2. Append a factual entry to docs/assist-curve/implementation-log.md using its template and update
   the phase status table.
3. Report changed files, verification performed, remaining work and any deviations from the plan.

Do not mark the phase Verified unless every completion criterion and relevant repository-wide check
passes. If a clean implementation conflicts with the phase plan or current architecture, stop at
the smallest safe point, record the pressure clearly, and ask for a decision rather than hiding it
behind another abstraction.
```

## Optional phase-specific context

Add only context that changes implementation choices, such as:

- An explicitly approved departure from the version-1 fixed speed grid in the Phase 1 document.
- Whether the task is a deliberately smaller slice than the complete phase.
- A known worktree change the agent must preserve.
- A failed check or unresolved decision from the latest implementation-log entry.

Do not paste the entire roadmap into the prompt; the agent is required to read the source documents.
