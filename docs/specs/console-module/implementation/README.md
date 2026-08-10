# Coordinator and console split implementation workflow

Status: draft orchestration instructions.

This directory is the complete handoff for a fresh orchestration agent. Execute it rather than
restating it. Product and repository instructions override workflow documents when they conflict.

## Source of truth

Read these before starting:

1. [Approved feature specification](../../console-module.md)
2. [Implementation plan](plan.md)
3. The next numbered workstream record in the plan
4. [Repository context](../../../../PROJECT_CONTEXT.md)
5. [Root README](../../../../README.md)
6. [Frontend instructions](../../../../frontend/AGENTS.md) before any frontend work
7. [Unified controller architecture](../../../decisions/0008-unified-controller-architecture.md)
8. [Accessory isolation](../../../decisions/0009-isolate-coordinator-accessories-from-control.md)
9. [Constrained network exposure](../../../decisions/0010-constrain-hotspot-ui-exposure.md)

Also follow the repository-level `AGENTS.md` instructions supplied to the agent even though they
are not checked into this repository. The approved specification defines product scope; this
workflow defines execution ownership and review.

## Roles

### Orchestrator

The orchestrator owns specification interpretation, branch/base tracking, sequential assignment,
cross-workstream contracts, finding triage, accepted commits, final review and completion
reporting. It must not become an unplanned implementation owner.

### Implementation agent

One fresh implementation agent owns one numbered workstream through at most one remediation pass.
It reads this README, the plan, its frozen packet and accepted dependency handoffs; implements the
smallest complete change; runs targeted verification; performs a deletion/simplification pass; and
records a concise handoff in its numbered file.

### Independent reviewer

A different fresh agent reviews the uncommitted workstream diff and surrounding code. It may edit
only the `Independent review` and later `Closure review` sections of that workstream record. It
does not change implementation files.

Findings are classified as:

- **Required:** correctness defect, unmet acceptance criterion, boundary violation, meaningful
  regression or unjustified complexity that blocks acceptance.
- **Optional:** useful but nonessential or out-of-scope improvement; it does not block acceptance.
- **Question:** ambiguity requiring orchestrator judgment before classification.

Review findings are evidence. The orchestrator validates and triages them against the approved
specification.

## Branch and commit model

- Integration branch: `feature/coordinator-console-split`
- Starting commit: the clean approved HEAD recorded in [plan.md](plan.md)
- Workstreams run sequentially unless the plan is explicitly amended with disjoint ownership.
- Agents must not edit the shared worktree concurrently.
- Before each stream, require a clean head containing all prior accepted implementation and
  bookkeeping commits.
- Keep implementation, review and remediation changes uncommitted so the reviewer sees one
  coherent diff.
- After closure acceptance, the implementation agent runs final targeted checks and creates one
  coherent implementation commit following repository conventions.
- The orchestrator then records that commit hash in the workstream and plan in a separate small
  workflow-bookkeeping commit.
- Never absorb unrelated dirty-worktree changes. Stop the stream until ownership is resolved.

## Per-workstream loop

Use exactly this bounded loop:

```text
implementation
    -> independent review
    -> one remediation pass if required
    -> focused closure review
    -> accept or escalate to orchestrator
```

There is no automatic third review loop. Closure checks accepted findings and release-blocking
defects introduced by their fixes; it does not reopen optional improvements. Persistent
disagreement returns to the orchestrator.

### Start

The orchestrator records the clean base and changes the plan/workstream status to `Implementing`.
It gives the implementation agent this prompt:

```text
Implement the next workstream from its frozen task packet. Read the workflow README, plan,
specification and accepted dependency handoffs first. Stay within initial ownership and required
seams. Keep changes uncommitted, run targeted verification, simplify the result, and complete the
Implementation handoff section. Do not start adjacent workstreams.
```

### Independent review

After handoff, set status to `Review` and give a fresh reviewer:

```text
Independently review this workstream's uncommitted diff against its task packet, the approved
specification and surrounding code. Run proportionate checks. Do not edit implementation files.
Record Required, Optional and Question findings with evidence in the Independent review section.
Reject speculative abstractions as well as functional defects.
```

### Remediation and closure

If required findings are accepted, set status to `Remediation` and send one batch to the original
implementer:

```text
Resolve the orchestrator-accepted findings in one pass. Revisit and simplify the affected design;
do not accumulate wrappers, aliases, flags, compatibility paths or special cases to preserve a
flawed first version. Update Resolution and rerun focused verification.
```

Then set status to `Closure review` and return to the original reviewer:

```text
Perform focused closure on accepted findings and their fixes. Check for release-blocking defects
introduced by remediation. Do not restart open-ended review or promote optional observations.
Record the closure verdict.
```

If there are no required findings, record that no remediation was needed and proceed directly to
closure.

### Accept and commit

The orchestrator accepts only a passing closure. The implementer reruns final targeted checks and
commits. The orchestrator records the hash and status `Accepted` in a separate bookkeeping commit,
then starts the next workstream from that clean head.

## Final whole-feature review

After all five workstreams are accepted, assign a new reviewer to
[final-review.md](final-review.md). That reviewer audits the complete branch against the recorded
starting commit and specification. The orchestrator assigns every accepted correction to its
original workstream owner in one batch. The same final reviewer performs focused closure. There is
no open-ended second whole-feature review.

## Completion report

The orchestrator reports:

- Delivered coordinator and console outcomes
- Accepted implementation commits
- Verification run and results
- Hardware and in-vehicle validation still pending
- Specification drift and its approval, or explicitly none
- Deferred optional observations

