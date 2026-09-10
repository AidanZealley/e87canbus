# Device lifecycle tooling whole-feature review

Status: not started. Begin only after every workstream and external gate is accepted.

## Reviewer task packet

Review the complete integration branch against the recorded starting commit and all three approved
product documents. Read accepted handoffs and external evidence, but independently inspect the
combined diff and surrounding code.

Audit CLI/package boundaries, destructive-disk safety, secret lifecycle, cryptographic identity,
strict artifact validation, first-boot atomicity, unique host identity, application packaging,
network isolation, TLS and application authorization, console failure behavior, status accuracy,
dependency direction, generated contracts, test value, documentation agreement and deletion of
the superseded path.

Confirm that recovery packages, private keys, passwords, images and bundles are absent from Git and
logs. Treat recorded macOS and Pi results as external evidence; do not infer hardware success from
fixtures. Reject optional hardening that exceeds the approved threat model unless it exposes a
concrete acceptance or correctness failure.

Run the repository-wide commands from workstream 7 and any focused checks needed to investigate
the final diff. Record unavailable platform checks honestly rather than substituting weaker claims.

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

Return each accepted correction to its original workstream owner in one batch. Use a new owner only
when the original is unavailable, and record why.

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

