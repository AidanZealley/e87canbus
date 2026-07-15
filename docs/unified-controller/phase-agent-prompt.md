Work on Phase [N — NAME] of the unified-controller roadmap.

Primary specification:
docs/unified-controller/[PHASE-DOCUMENT].md

Before changing code, read:

- PROJECT_CONTEXT.md
- applicable AGENTS.md files
- docs/unified-controller/README.md
- the complete primary phase document
- the status table and Current handoff in
  docs/unified-controller/implementation-log.md
- the newest entry for the immediately preceding phase
- the unified-controller ADR created by Phase 1 or ADRs 0001–0007 if working on Phase 1
- any additional ADRs explicitly listed by the phase document

Read older implementation-log entries only when the current handoff, phase document,
repository state or a discovered conflict points to them.

Inspect current code, tests and git status before designing changes. The specification
defines the required outcome, not permission to overwrite newer work.

Universal boundaries:

- Operational state has one bounded, ordered owner.
- Simulation replaces adapters/devices and never edits controller state directly.
- Default live composition remains unable to transmit.
- Do not introduce unverified BMW or physical steering behaviour.
- Preserve unrelated worktree changes.
- Implement this phase only.

Before implementation, report:

1. Intended outcome and non-goals.
2. Expected files and public contracts.
3. Existing changes to preserve.
4. Compatibility introduced or removed.
5. Planned verification.

Implement the phase with the simplest code that satisfies its contracts. Avoid generic
frameworks, duplicate state ownership, unbounded retention and speculative abstractions.
Ensure new features or refactors are implemented cleanly with no trace of older features
they may have replaced. Do not leave facades.

At completion:

1. Check every phase completion criterion.
2. Update the implementation-log status table and Current handoff.
3. Add a newest-first factual log entry using its template.
4. Report changes, contracts, dependencies/migrations, verification, compatibility and
   remaining work.
5. Mark Verified only when every required check and acceptance condition passes.

If the phase conflicts with current code or an accepted ADR, stop at the smallest safe
point and request a decision rather than hiding the conflict.
