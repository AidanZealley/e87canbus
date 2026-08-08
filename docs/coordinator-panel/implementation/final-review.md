# Coordinator panel whole-feature review

Status: not started. Begin only after workstreams 1–5 are accepted.

## Reviewer task packet

Review the complete implementation branch against the starting commit recorded in
[plan.md](plan.md), the [context](../context.md), and the [specification](../spec.md). Read every
accepted workstream handoff, but independently inspect the combined diff and surrounding code.

This is a whole-feature review, not permission to expand the feature. Evaluate:

- Completeness against every specification acceptance criterion.
- One shared panel service, hotspot service, and display derivation in production and simulation.
- The absence of panel/hotspot knowledge in the coordinator kernel.
- Correct dependency direction and thin seams at snapshots, backends, UART, and frontend state.
- Cross-workstream lifecycle behaviour at startup, readiness, fatal state, button handling, and
  graceful shutdown.
- Agreement between Python UART output, firmware parsing, setup paths, packages, permissions, and
  documentation.
- Whether failures remain isolated from coordinator readiness and CAN processing.
- Type safety, readable top-level control flow, and repository convention fit.
- Simplification opportunities created only by combining the workstreams: duplicated state,
  adapters with no second implementation, façade exports, obsolete mocks, speculative recovery,
  excessive configuration, and tests coupled to implementation details.

Run verification proportional to the assembled change. Broad repository checks are appropriate
here if they are part of normal project validation, but do not invent exhaustive fault matrices.
Never claim physical validation without evidence.

## Finding rules

Classify each item as `Required`, `Optional`, or `Question` using the definitions in
[README.md](README.md). Required findings include evidence, consequence, the violated requirement
or risk, and the smallest coherent correction. Group findings by owning workstream.

Do not edit implementation files. Complete the review record below and return the verdict to the
orchestrator.

## Initial whole-feature review

- Reviewer: `TBD`
- Branch and starting commit: `TBD`
- Reviewed head: `TBD`
- Verification run: `TBD`
- Acceptance-criteria audit: `TBD`
- Required findings by owner: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`
- Verdict: `TBD`

## Orchestrator triage

- Accepted required findings and assigned owners: `TBD`
- Rejected findings and reasons: `TBD`
- Deferred optional observations: `TBD`
- Specification drift requiring Aidan's decision: `TBD`

Each affected owner receives all of its accepted findings together and performs one coherent pass.
Owners update their workstream `Resolution` with the additional final-review work and verification.

## Focused closure

The same final reviewer verifies only the orchestrator-accepted findings and checks that their
corrections introduced no release-blocking defect. It does not conduct a second open-ended review.

- Reviewed head: `TBD`
- Finding outcomes: `TBD`
- Final simplification assessment: `TBD`
- Remaining blockers: `TBD`
- Verdict: `TBD`

## Orchestrator completion record

- Final head: `TBD`
- Final verification: `TBD`
- Hardware validation still pending: `TBD`
- Specification drift: `TBD`
- Completion report delivered: `TBD`
