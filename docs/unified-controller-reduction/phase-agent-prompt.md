Work on Phase [N — NAME] of the unified-controller reduction roadmap.

Primary specification:
docs/unified-controller-reduction/[PHASE-DOCUMENT].md

Before changing code, read:

- PROJECT_CONTEXT.md
- applicable AGENTS.md files
- docs/unified-controller-reduction/README.md
- the complete primary phase document
- the status table and Current handoff in
  docs/unified-controller-reduction/implementation-log.md
- the newest entry for the immediately preceding phase
- docs/unified-controller/README.md and its newest final-review log entry
- ADR 0008 and any additional ADRs explicitly listed by the phase document

Read older logs only when the current handoff, phase document, repository state or a discovered
conflict points to them. Inspect current code, tests and git status before proposing changes. Newer
work in the shared tree takes precedence over examples in the roadmap.

The purpose of this pass is not just architectural neatness. It must reduce the amount of code and
the number of concepts a maintainer must understand while preserving the verified behavior that
motivated the unified controller.

Universal boundaries:

- Operational state retains one bounded, ordered owner.
- HTTP retains commands/resources; Socket.IO retains live-state authority.
- The singleton frontend transport, reconnect snapshot and `boot_id` reset semantics remain.
- Engine.IO/publication/trace retention remains bounded; a slow peer cannot block the controller.
- Simulation continues through production codecs, transitions and effects.
- Default live composition remains unable to transmit.
- Do not introduce or claim unverified BMW or physical steering behavior.
- Preserve unrelated worktree changes.
- Implement this phase only.

Simplification rules:

- Delete before abstracting. Prefer removing a layer to adding a helper around it.
- Prefer direct, typed calls and framework-native mechanisms over repository-specific wrappers.
- Do not add a generic abstraction unless it replaces at least two concrete mechanisms, removes
  more production code than it adds and makes the common flow shorter.
- Do not create a new model, projection, result wrapper, queue, manager, service or configuration
  switch without naming the old concept it removes.
- Do not keep compatibility aliases, forwarding functions, parallel payloads or deprecated imports.
- Do not game the budget by moving code, generating it, compressing formatting, weakening types,
  deleting safety behavior or deleting valuable contract tests.
- Tests should protect observable behavior, public contracts, bounds and safety. Remove tests of a
  private structure when that structure is deleted; do not recreate it to keep the test green.
- Treat tests whose only purpose is proving a retired implementation, route, field or import did not
  return as presumptively removable. Retain a negative regression only when absence is itself a
  current public, security, safety or ownership contract.
- Do not preserve production factories, accessors, serializers or dependency seams solely to keep
  tests convenient. Adapt or delete the test.
- Do not replace every deleted low-value test one-for-one. One boundary-level behavior test may
  supersede many private-layer assertions.
- A rename, directory shuffle or split/merge with no reduced concept count is not a reduction.
- Every implementation phase should be net-negative in production lines. If it is not, stop and
  explain why before asking to mark the phase complete.

Before implementation, report:

1. Observable behavior and safety invariants that will remain unchanged.
2. The exact concepts, wrappers, files or contract copies proposed for deletion.
3. The phase-base production line/file counts and the planned deletion budget.
4. Every new production symbol or file proposed; the default answer is `None`.
5. The current and intended common-flow hop count.
6. Tests that remain authoritative and tests expected to disappear with deleted internals.
   Classify retained tests by public behavior, safety, concurrency/bounds, real bug regression or
   useful domain example; tests with no such classification require a deletion justification.
7. Existing worktree changes that must be preserved.

During implementation, keep a small reduction ledger. For each addition, identify the larger
deletion it enables. If an addition stops enabling that deletion, remove the addition.

At completion:

1. Check every phase completion criterion and every protected behavior touched by the phase.
2. Run the phase verification and relevant repository-wide checks.
3. Update the implementation-log status table and Current handoff.
4. Add a newest-first factual log entry using its template.
5. Report a before/after table for production lines, files, named concepts, flow hops and contract
   copies; distinguish tests/docs/generated files from production code.
6. List production additions as well as deletions and explain why each surviving addition was
   necessary.
7. Report test files/lines/count/runtime before and after. Explain removed value, not just volume.
8. Run dead-symbol/import/documentation searches for every removed concept.
9. Mark `Verified` only when behavior passes and the simplification is measurable.

The phase is blocked, not complete, when:

- its production diff is net-positive without prior approval;
- a protected bound, safety gate or reconnect behavior would need to be weakened;
- current code or an accepted ADR contradicts the planned deletion; or
- the result moves complexity rather than removes it.

Do not conceal those conflicts behind a new facade. Stop at the smallest safe point and request a
decision.
