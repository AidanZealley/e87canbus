# Simulated independent button pad whole-feature review

Status: not started. Begin only after every workstream is accepted.

The final-review lead owns the Final row in [plan.md](plan.md), triages the findings, sends each
accepted correction to a fresh implementation agent, runs focused closure, writes this record and
makes one commit.

## Reviewer task packet

Review the full branch against the starting commit recorded in [plan.md](plan.md) and the approved
Slice 02 sources. Read accepted handoffs, but independently inspect the combined diff and surrounding
code.

Audit specification completeness, preservation of the accepted Slice 1.5 boundary and vehicle CAN,
certificate identity and authorization, scene semantics, retained desired steering
state, migration safety, generation durability, status receipt, canonical press dispatch, initial
SSE ordering, bounded consumers, lifespan teardown, nginx and generated contracts, simulation
composition, dependency direction, stale mocks and meaningful tests.

Trace these cases end to end rather than accepting layer-local tests:

- a fresh simulated identity starts, authenticates, receives and validates the current scene, then
  reports the applied generation;
- a profile or application-state change that changes the steady scene advances and publishes once;
- reconnect and coordinator restart preserve generation;
- a simulated tap crosses HTTP once and reaches the active profile's intent once;
- press feedback does not become a configuration document;
- desired steering state still changes without claiming an applied hardware value; and
- repository-wide searches confirm the workflow did not reintroduce the generated custom protocol,
  coordinator-device ISO-TP, device registry/lifecycle, legacy project-device firmware or a
  project-device CAN simulation path.

Confirm the result uses direct role-specific code for the one implemented device. Reject a role
plugin system, event log, shared generic SSE framework, replay protocol, presence tracking, auth
bypass, transport-neutral payload store or configuration point without an approved requirement.

## Review briefs

Initial whole-feature review:

```text
Act as the whole-feature reviewer for the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/README.md, plan.md, all six accepted workstream records, docs/specs/independent-devices-v2/slices/02-simulated-button-pad.md, architecture-and-boundaries.md, live-and-device-api.md, first-device-delivery.md, the accepted Slice 1.5 handoff and the ADRs linked by the README. Review the complete branch diff against the starting commit recorded in the plan and inspect surrounding code. Run proportionate read-only checks. Write findings only in this file's Initial whole-feature review section. Audit that the accepted coordinator-device CAN, generated custom protocol, ISO-TP, registry/lifecycle, legacy firmware and project-device simulator removals remain intact; preservation of vehicle CAN and desired steering state; certificate identity and closed authorization; exact feedback-free scene semantics; SQLite migration and generations; status receipt; canonical direct button input; initial SSE ordering; bounded consumers; lifecycle; nginx; OpenAPI and generated artifacts; production-path simulation; dependency direction; stale mocks and unjustified machinery. Return a verdict followed by evidence-backed Required findings grouped by original workstream owner, Optional observations and Questions.
```

Focused closure review:

```text
Perform the focused whole-feature closure review for the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/final-review.md, including the Initial whole-feature review and Lead triage, plus the affected workstream Resolution records. Inspect the cumulative branch diff against the starting commit. Verify every accepted Required finding and check those corrections for release-blocking defects and unnecessary compatibility or generic machinery. Do not reopen optional suggestions or perform another open-ended review. Write the verdict only in this file's Focused closure section. Return a final verdict and any remaining blockers with evidence.
```

## Final verification

Run from the repository root:

```text
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

No external validation gate follows this review. Hardware, real nginx mutual TLS, Wi-Fi, device
flash and physical CAN belong to later slices and must not be claimed here.

## Initial whole-feature review

- Reviewer: `TBD` (fresh lead subagent)
- Branch, base and reviewed head: `TBD`
- Verification run: `TBD`
- Acceptance-criteria audit: `TBD`
- Required findings by owner: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`
- Verdict: `TBD`

## Lead triage

- Accepted findings and owners: `TBD`
- Rejected findings and reasons: `TBD`
- Deferred optional observations: `TBD`
- Drift requiring user decision: `TBD`

## Correction evidence

- Owner, correction and focused verification: `TBD`

## Focused closure

- Reviewed head: `TBD`
- Finding outcomes: `TBD`
- Final simplification assessment: `TBD`
- Remaining blockers: `TBD`
- Verdict: `TBD`

## Completion record

- Final verification: `TBD`
- External validation pending: None for Slice 02.
- Specification drift: `TBD`
