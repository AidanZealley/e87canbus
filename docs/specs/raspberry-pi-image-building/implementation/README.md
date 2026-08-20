# Raspberry Pi image-building implementation workflow

Status: draft orchestration instructions.

This directory is the complete handoff for a fresh orchestration agent. Execute it only after the
specification and workflow have been committed to a clean starting branch.

## Source of truth

Read these in order:

1. Repository instructions supplied to the agent.
2. [Raspberry Pi image-building specification](../../raspberry-pi-image-building.md).
3. [Implementation plan](plan.md).
4. The next numbered workstream in the plan.
5. [Current deployment runbook](../../../../deploy/README.md),
   [host setup guide](../../../../docs/setup.md), and the existing setup scripts named by that
   workstream.

The product specification overrides this workflow. Record a conflict in the plan and ask Aidan
only when resolving it would change approved behavior or architecture. Agents may choose pinned
tool versions, exact package lists and focused checks when those choices preserve the spec.

## Roles

The orchestrator owns source-of-truth interpretation, the integration branch, dependency order,
agent assignments, finding triage, cross-workstream decisions, checkpoint coordination, final
review and completion reporting. It should not become an unplanned implementation owner.

Each implementation agent owns one workstream through one remediation pass. It implements the
smallest complete change, runs the targeted checks, removes duplicated or speculative machinery
and records its handoff in the workstream file.

A different fresh agent reviews each workstream. The reviewer inspects the full uncommitted diff
and relevant surrounding code. It may edit only the `Independent review` and `Closure review`
sections of its assigned record. Findings use these categories:

- Required: correctness defects, unmet acceptance criteria, boundary violations, meaningful
  regressions or unjustified complexity that blocks acceptance.
- Optional: useful work outside the required result. It does not block acceptance.
- Question: an ambiguity for orchestrator judgment.

## Branch and commit model

Use the integration branch `feature/pi-image-building`. Record its starting commit in
[plan.md](plan.md). Do not start while the worktree contains changes outside the committed workflow
and specification.

Run workstreams sequentially. Agents must not edit the shared worktree concurrently. Keep each
implementation uncommitted through implementation, review, remediation and closure so the reviewer
sees one coherent diff.

After acceptance, the implementation agent creates one implementation commit. The orchestrator
then records that hash in the workstream and plan using a small bookkeeping commit. Start the next
stream from the clean head containing both commits.

Hardware checkpoints are the one exception. After implementation review and closure, create and
push a checkpoint candidate commit so Aidan can test the exact tree on the MacBook. Keep the
workstream in `Closure review` until the hardware result is recorded. A successful result accepts
that candidate. A failed result returns one focused correction to the original owner and one
focused check to the original reviewer before a new candidate is pushed.

Generated images and caches never enter a commit. Aidan's checkpoint results belong in the
relevant workstream record.

## Per-workstream loop

1. **Start.** The orchestrator checks dependencies, records the base commit and assigns one fresh
   implementation agent.
2. **Implement.** The agent changes only its owned files and agreed integration exceptions, runs
   targeted checks, simplifies the result and fills in `Implementation handoff`.
3. **Review.** A different fresh agent reviews the uncommitted diff and records required findings,
   optional observations and questions.
4. **Remediate.** The orchestrator triages the review. The original implementation agent resolves
   all accepted required findings in one batch and records dispositions and verification.
5. **Close.** The original reviewer checks only accepted findings and release-blocking defects
   introduced by their fixes.
6. **Accept or escalate.** The orchestrator accepts the stream or resolves persistent disagreement.
   There is no automatic third review loop.
7. **Commit.** The implementation agent verifies and commits. For a hardware checkpoint, push the
   candidate and wait for its result before marking it accepted. The orchestrator records the
   accepted hash.

Remediation must revisit the affected design. Do not accumulate flags, wrappers, aliases or
compatibility paths to preserve a flawed first attempt.

### Implementation prompt

```text
Implement the next ready workstream in the Raspberry Pi image-building workflow. Read the workflow
README, plan, approved specification, task packet and its dependency handoffs. Work only in the
assigned files and agreed exceptions. Keep changes uncommitted, run the targeted verification,
perform a simplification pass and complete the implementation handoff. Stop for any checkpoint or
material specification drift named by the task packet.
```

### Review prompt

```text
Independently review the current uncommitted workstream diff against its task packet, the approved
specification and surrounding deployment code. Do not edit implementation files. Record required
findings, optional observations, questions and evidence in the workstream's review section.
```

### Closure prompt

```text
Perform the focused closure review for this workstream. Verify accepted findings and their fixes,
then check only for release-blocking defects introduced by remediation. Update the closure section.
Do not begin another broad review or promote optional observations.
```

## Checkpoint handling

Workstream 1 pauses after producing the base-image checkpoint commit. Aidan builds it on the M1 Pro,
flashes it with Raspberry Pi Imager and boots a Raspberry Pi 4. Record the command, artifact digest,
result and useful failure output in that workstream before acceptance.

Workstream 5 pauses for the two final role-image checks. Route a failed check to the workstream that
owns the defective behavior. Use one focused correction and closure review rather than restarting
all reviews. Hardware success is required before final completion.

## Final whole-feature review

After all workstreams are accepted, assign a new reviewer to follow
[final-review.md](final-review.md). The reviewer inspects the complete branch from the recorded
starting commit. The orchestrator triages findings and returns each accepted correction to its
original owner in one batch. The same reviewer performs focused closure.

## Completion report

Report the image-building commands and artifacts, accepted commits, automated verification,
MacBook and Pi checkpoint evidence, specification drift, known limitations and deferred optional
observations. State plainly if any external check remains. Do not call the workflow complete while
either hardware checkpoint is pending.
