# Provisionable offline button pad whole-feature review

Status: not started. Begin after all three workstreams and hardware gates are accepted.

## Reviewer task packet

Review the full integration branch against the starting commit in `plan.md` and the approved
Slice 03 sources. Read accepted handoffs, but independently inspect the combined diff and nearby
code. Audit specification completeness, partition and manifest consistency, scene validation,
boot ordering, receive-only CAN, certificate identity, flash safety, obsolete AVR removal,
dependency direction, tests and documentation. Confirm physical evidence is recorded without
claiming a software test proves it. Run `uv run pytest -q`, `uv run mypy`,
`uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py`, and the firmware build
command when available. Report Required, Optional and Question findings with evidence and owner.

## Initial whole-feature review

- Reviewer: `TBD`
- Branch, base, and reviewed head: `TBD`
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

## Focused closure

- Reviewed head: `TBD`
- Finding outcomes: `TBD`
- Final simplification assessment: `TBD`
- Remaining blockers: `TBD`
- Verdict: `TBD`

## Completion record

- Final verification: `TBD`
- External validation pending: `TBD`
- Specification drift: `TBD`
