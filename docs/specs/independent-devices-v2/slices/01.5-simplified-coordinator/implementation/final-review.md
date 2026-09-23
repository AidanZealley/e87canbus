# Simplified coordinator whole-feature review

Status: not started. Begin only after every workstream is accepted.

The final-review lead owns the Final row in [plan.md](plan.md), triages the findings,
sends each accepted correction to a fresh implementation agent, runs focused closure, writes this
record and makes one commit.

## Reviewer task packet

Review the complete branch against the starting commit in [plan.md](plan.md), Slice 1.5, ADR 0018
and the linked product documents. Read accepted handoffs, then independently inspect the cumulative
diff and surrounding code.

Audit complete removal, the fresh-database empty profile seed, retained desired state, vehicle decoding,
single-owner ordering, runtime lifecycle, browser contracts, generated artifacts, dependency
direction, stale mocks and unjustified machinery.

Trace these cases end to end:

- a fresh database contains one selected `Default` profile with sixteen unassigned slots;
- vehicle frames retain network and ingress time, decode once and update the browser projection;
- desired steering, curve and profile changes work without a device registry or actuator;
- browser SSE publishes complete current projections with its one boot-scoped revision source;
- live startup creates no CAN transmitter or output executor; and
- simulation supplies vehicle input without project-device peers or a second state owner.

Search the full repository for the removed command, custom protocol, registry, ISO-TP, old firmware,
`DeviceRole`, `DeviceSource`, device lifecycle and catalogue types, effect execution, applied
Servotronic, lighting topic and project-device simulation controls.

Confirm every retained kernel concern supports vehicle observations, desired intents, profiles and
curves, or complete publication projections. Reject compatibility facades, no-op shells, empty
unions, generic output hooks and configuration retained only for a hypothetical vehicle action.

## Review briefs

Initial whole-feature review:

```text
Act as the whole-feature reviewer for the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/README.md, plan.md, all four accepted workstream records, Slice 1.5, ADR 0018 and every source linked by the README. Review the complete branch diff against the starting commit and inspect surrounding code. Run proportionate read-only checks. Write findings only in this file's Initial whole-feature review section. Audit removal of high-beam and command-specific defaults; the fresh-database selected empty Default profile; complete removal of button-pad and Servotronic transport and execution; deletion of DeviceRole, DeviceSource, custom protocol, registry, ISO-TP, old firmware, project-device simulation and effect machinery; preservation of desired steering, profiles, curves and vehicle observations; single-owner ordering; runtime lifecycle; browser SSE revisions; generated contracts; dependencies; stale mocks; and unjustified abstractions. Trace the specified end-to-end cases and classify evidence-backed findings as Required, Optional or Question, grouped by original workstream owner.
```

Focused closure review:

```text
Perform the focused whole-feature closure review for the simplified coordinator workflow. Read final-review.md including the Initial whole-feature review and Lead triage, plus affected workstream Resolution records. Inspect the cumulative branch diff against the recorded starting commit. Verify every accepted Required finding and check its correction for release-blocking database seed, ownership, vehicle-decoding, publication, lifecycle or incomplete-deletion defects. Do not reopen optional suggestions or perform another open-ended review. Write the verdict only in this file's Focused closure section. Return a final verdict and any remaining blockers with evidence.
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

No hardware or vehicle validation follows this review. This slice removes unverified output and must
not claim a physical actuation result.

## Initial whole-feature review

- Reviewer: `TBD`
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
- External validation pending: None for Slice 1.5.
- Specification drift: `TBD`
