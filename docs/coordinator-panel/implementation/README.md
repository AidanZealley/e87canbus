# Coordinator panel implementation workflow

Status: approved orchestration instructions.

This directory is the complete handoff for implementing the minimal coordinator panel. A fresh
orchestration agent should be able to start here without relying on conversation history.

Use [the starter prompt](starter-prompt.md) to hand this workflow to a fresh orchestration thread.

## Source of truth

Read these files completely before starting:

1. The repository `AGENTS.md` instructions supplied to the agent.
2. [Coordinator panel context](../context.md).
3. [Minimal coordinator panel specification](../spec.md).
4. [Implementation plan](plan.md).
5. The task packet for the next workstream.

The context and specification define the product. These workflow files divide the work; they do
not override the specification. If they conflict, stop that workstream and have the orchestrator
resolve the documents before implementation continues.

## Roles

### Orchestrator

The orchestrator owns interpretation of the request, specification, and acceptance criteria. It:

- Creates or verifies the implementation branch and records its starting commit in `plan.md`.
- Keeps the status table current.
- Starts only work whose dependencies are accepted.
- Gives every agent the relevant task packet and immutable source-of-truth links.
- Ensures file ownership does not overlap between active agents.
- Triages review findings rather than forwarding them as unquestioned instructions.
- Resolves scope questions and reviewer/implementer disagreement.
- Runs the final whole-feature review and reports completion and drift to Aidan.

The orchestrator should coordinate rather than become an unplanned implementation agent. It may
make tiny workflow-document corrections, but product changes should go back to the workstream owner
so responsibility remains clear.

### Implementation agent

One fresh agent owns each workstream through its remediation pass. It:

- Reads the source of truth, this workflow, its task packet, and accepted dependency handoffs.
- Inspects relevant existing code before choosing the smallest compatible implementation.
- Changes only its owned area and explicitly listed integration seams.
- Runs targeted verification.
- Completes the `Implementation handoff` section of its workstream file.
- Validates review findings and performs one coherent remediation pass when required.
- Completes `Resolution` and the final verification record.

The implementation agent must not silently broaden scope. A material choice not settled by the
specification goes to the orchestrator before it is built.

### Review agent

A different fresh agent reviews each workstream. It does not edit implementation files. It may edit
only the `Independent review` and `Closure review` sections of the assigned workstream record.

The reviewer treats the specification and acceptance criteria as the source of truth. Findings are
evidence for the orchestrator, not automatic work orders. The reviewer distinguishes:

- **Required:** a correctness defect, unmet acceptance criterion, boundary violation, meaningful
  regression, or unjustified complexity that must change.
- **Optional:** a reasonable improvement that is not needed for this scope. It is not included in
  remediation unless the orchestrator promotes it.
- **Question:** ambiguity requiring orchestration judgment before it can be classified.

Every required finding includes evidence, consequence, the violated requirement or risk, and the
smallest coherent correction. Reviews should examine the diff and enough surrounding code to judge
fit, not merely comment on style.

## Branch and commit model

Use one feature integration branch and execute workstreams sequentially. Record the branch and base
commit in [plan.md](plan.md). Parallel work is not the default; it is allowed only when the
orchestrator has assigned non-overlapping files and independent state.

For each workstream:

1. Begin from the clean, accepted integration-branch head.
2. Record that commit as the workstream base.
3. Leave implementation changes uncommitted through implementation, review, and remediation so
   the reviewer can assess one coherent diff.
4. After closure acceptance, have the implementation agent create one coherent workstream commit.
5. The orchestrator records that commit in the workstream and plan, then makes one small workflow-
   record commit. A commit cannot contain its own final hash, so this bookkeeping is necessarily
   separate from the implementation commit.
6. Confirm the worktree is clean before starting the next stream. The next workstream base includes
   both accepted commits.

Do not hide unrelated user changes, rewrite shared history, or combine another workstream's changes
into the commit. If unrelated changes are present, the orchestrator resolves ownership before work
continues.

## Per-workstream loop

Keep the implementation agent and reviewer identities for the duration of one workstream. The
orchestrator should use this agent sequence:

1. Start one fresh implementation agent with the task packet.
2. Wait for its completed implementation and handoff.
3. Start a different fresh review agent with the base commit and current diff.
4. If needed, return accepted findings to the original implementation agent for one remediation
   turn.
5. Return the result to the original reviewer for focused closure.
6. Return to the implementation agent once more only to record final verification and commit the
   accepted workstream.

Never let implementation and review agents edit the shared worktree concurrently. Agent summaries
help the orchestrator coordinate, but the checked-in workstream record is the durable handoff and
must contain every fact needed by the next agent.

### 1. Start

The orchestrator confirms dependencies, ownership, clean status, and the base commit. It sets the
workstream to `Implementing` in `plan.md` and gives the implementation agent:

- The specification and workflow paths.
- The workstream file.
- Its base commit.
- Any accepted dependency handoffs it must read.
- An instruction to finish code, targeted tests, and the handoff in one focused pass.

A suitable implementation prompt is:

> Implement only the assigned workstream from its recorded base. Read the context, specification,
> workflow README, task packet, and accepted dependency handoffs completely. Preserve the stated
> ownership and non-goals. Finish the smallest complete implementation, targeted verification,
> simplification pass, and Implementation handoff. Do not commit yet. Stop and report if a material
> choice would change the specification or cross-workstream contract.

### 2. Implementation handoff

The agent records only information another agent needs:

- Outcome and files changed.
- Non-obvious decisions and why the direct approach was insufficient.
- Commands run and their results.
- Known limitations that are intentional under the specification.
- Any drift or `None`.

Do not write a chronological diary, paste terminal output, or restate the complete spec.

### 3. Independent review

The orchestrator sets status to `Review` and gives a fresh reviewer the workstream base, current
working tree, task packet, implementation handoff, and review rules above.

The reviewer checks:

- Observable correctness and acceptance criteria.
- Adherence to scope and module boundaries.
- Type safety, readable control flow, and consistency with repository conventions.
- Duplicated state or simulator-only business logic.
- Abstractions, configuration, retries, and tests not justified by the specification.
- Missing deletion or documentation updates made necessary by the change.

The verdict is `Accepted` or `Changes required`. Optional observations never prevent acceptance.

A suitable review prompt is:

> Review this workstream independently against its base commit, task packet, context, and
> specification. Inspect the diff and surrounding code; run proportionate targeted checks. Do not
> edit implementation files. Record evidence-backed Required, Optional, and Question findings in
> the Independent review section. Optional improvements do not block acceptance. Return one
> Accepted or Changes required verdict.

### 4. One remediation pass

When changes are required, the orchestrator validates and triages the findings, then sends only
accepted required findings to the original implementation agent. The agent addresses them together
and updates `Resolution`.

The remediation instruction is:

> Revisit the affected design and make the smallest coherent correction. Do not preserve a flawed
> structure by layering wrappers, flags, aliases, compatibility paths, or special cases onto it.
> Delete machinery and implementation-detail tests made obsolete by the correction, then reread
> each changed function as a whole.

Rejected findings are recorded with a short reason. Optional findings remain optional.

### 5. Closure review

The same reviewer performs one focused closure review. It verifies accepted required findings and
checks that their fixes did not introduce a release-blocking defect. It does not start another
open-ended review or promote new optional improvements.

If disagreement remains, or a new material defect is discovered, the reviewer records it and the
orchestrator decides. There is no automatic third loop.

A suitable closure prompt is:

> Verify only the orchestrator-accepted required findings and ensure their corrections introduced
> no release-blocking defect. Do not reopen general review or promote optional observations. Update
> Closure review with an Accepted or Escalate verdict.

### 6. Accept and commit

Once accepted, the implementation agent runs final targeted verification, updates the record,
commits the complete workstream with `Accepted commit` left pending, and reports the commit. The
orchestrator verifies it, records its hash in the workstream and plan, marks the workstream
`Accepted`, and commits that workflow bookkeeping. It then verifies a clean worktree and advances
the plan.

## Final whole-feature review

After all five workstreams are accepted, a new reviewer follows [final-review.md](final-review.md)
and reviews the complete branch against its recorded starting commit. This is the only open-ended
review of the assembled feature.

The orchestrator triages its findings and assigns each accepted required correction to the
implementation agent that owns the affected responsibility. Each owner gets one coherent fix pass.
The final reviewer then verifies only those accepted findings. Persistent disagreement returns to
the orchestrator; it does not create a review loop.

The final pass must include simplification across workstream boundaries: duplicate state, façade
exports, unused compatibility paths, simulator-only rules, excessive tests, and documentation that
no longer matches the implementation.

## Completion report

The orchestrator reports to Aidan:

- What each workstream delivered.
- Verification performed, including anything that still requires physical hardware.
- Whether the acceptance criteria are met.
- Any explicit specification drift and its disposition.
- Deferred optional observations, if they remain useful.

Do not describe ordinary implementation choices as drift. Drift means an observable requirement,
scope boundary, or agreed architecture changed.
