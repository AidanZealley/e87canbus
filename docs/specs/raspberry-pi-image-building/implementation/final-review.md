# Raspberry Pi image-building whole-feature review

Status: not started. Begin only after every workstream is accepted.

## Reviewer task packet

Review the full integration branch against the starting commit and the approved image-building
specification. Read the accepted handoffs, but independently inspect the combined diff and
surrounding deployment code.

Audit specification completeness, Docker privilege and mount boundaries, pinning, cache and
artifact behavior, manifest integrity, common and role ownership, secret exclusion, first-boot
behavior, service failure modes, Pi 4 hardware assumptions, duplicated setup state, test value and
documentation agreement.

Confirm that generated images and credentials are absent from Git. Check that the existing setup
scripts remain a deliberate migration fallback rather than a second undocumented image builder.
Treat the recorded MacBook, Imager and Pi results as external evidence. Do not infer hardware
success from structural tests.

Run proportionate whole-feature checks:

```bash
uv run pytest
uv run ruff check .
uv run mypy
uv run python scripts/generate_custom_protocol.py --check
cd frontend && pnpm api:check && pnpm lint && pnpm typecheck && pnpm test
```

If frontend dependencies are unavailable and the branch did not change frontend code or generated
contracts, record those checks as not run and justify that decision. Do not install or update
dependencies solely for review.

## Initial whole-feature review

- Reviewer: `TBD`
- Branch, base and reviewed head: `TBD`
- Verification run: `TBD`
- Acceptance-criteria audit: `TBD`
- Required findings by owner: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`
- Verdict: `TBD`

## Orchestrator triage

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

## Orchestrator completion record

- Final head and verification: `TBD`
- External validation pending: `TBD`
- Specification drift: `TBD`
- Completion report delivered: `TBD`
