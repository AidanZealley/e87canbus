# Device lifecycle tooling implementation workflow

Status: approved and in progress.

This directory is the complete handoff for a fresh orchestration agent.

## Source of truth

Read these in order:

1. Repository `AGENTS.md` instructions supplied to the agent.
2. [Device lifecycle tooling specification](../../device-provisioning.md).
3. [Wi-Fi device network supporting contract](../../wifi-device-network.md).
4. [Raspberry Pi host-images specification](../../raspberry-pi-image-building.md) and its accepted
   [v1 final review](../../raspberry-pi-image-building/implementation/final-review.md).
5. [Implementation plan](plan.md).
6. The next numbered workstream in the plan and accepted dependency handoffs.

Product specifications override workflow documents. Record any conflict in the plan. Ask Aidan
only when resolving it would change approved behavior, architecture or a security boundary.

## Roles

The orchestrator owns source-of-truth interpretation, the integration branch, workstream order,
file ownership, review triage, external gates, cross-workstream decisions and final reporting. It
must preserve the agreed simplicity boundary and reject optional machinery that does not protect an
explicit requirement.

Each fresh implementation agent owns one workstream through at most one remediation batch. It
implements the smallest complete result, runs focused checks, performs a deletion and
simplification pass and fills in that workstream's handoff.

A different fresh agent independently reviews each workstream. External reviewers run read-only;
the orchestrator records their results in `Independent review`. In-session closure reviewers may
edit only `Closure review`. Classify findings as:

- **Required:** a correctness or security defect, unmet acceptance criterion, boundary violation,
  meaningful regression or unjustified complexity that blocks acceptance.
- **Optional:** a useful idea outside the required result. It does not block acceptance.
- **Question:** an ambiguity for orchestrator judgment.

Agents must not edit the shared worktree concurrently.

## Branch and commit model

Use one integration branch, `feature/device-lifecycle-tooling`, created from the clean approved
specification commit. Record the full starting commit in [plan.md](plan.md).

Run workstreams sequentially from clean heads. Keep implementation changes uncommitted through
implementation, independent review, remediation and closure. After acceptance, the implementation
agent creates one coherent implementation commit. The orchestrator then records its hash in the
workstream and plan in a small bookkeeping commit. The next stream starts from the clean head that
contains both commits.

For an external gate, create and push an exact candidate commit after closure. Do not mark the
workstream accepted until its required evidence passes. Generated images, application bundles,
provisioning bundles, recovery packages and removable-media contents never enter Git.

## Per-workstream loop

1. **Start.** Check dependencies and a clean worktree, record the base commit and assign one fresh
   implementation agent.
2. **Implement.** Change only owned files and approved integration exceptions. Run targeted checks,
   simplify the result and complete `Implementation handoff`.
3. **Review.** Run the review command with a fresh prompt for the workstream. The reviewer inspects
   the entire uncommitted diff against the specifications, task packet and surrounding code.
4. **Remediate.** The orchestrator accepts or rejects findings with reasons. The original
   implementation agent resolves all accepted required findings in one batch.
5. **Close.** A fresh in-session reviewer checks the accepted findings and only release-blocking
   defects introduced by their fixes.
6. **Accept or escalate.** Accept the stream or resolve persistent disagreement. Do not start an
   automatic third review loop.
7. **Verify and commit.** The implementation agent reruns focused checks and commits. The
   orchestrator records the accepted hash separately.

Remediation must revisit the affected design. Do not accumulate flags, wrappers, aliases or
parallel paths merely to preserve a flawed first attempt.

### Implementation prompt

```text
Implement the next ready workstream in the device lifecycle tooling workflow. Read the workflow
README, plan, approved specifications, task packet and accepted dependency handoffs. Work only in
the assigned files and agreed exceptions. Keep changes uncommitted, run the targeted verification,
perform a deletion and simplification pass and complete the implementation handoff. Stop at a
documented external gate or material specification drift.
```

### Review prompt

```text
Independently review the current uncommitted workstream diff against its task packet, approved
specifications and surrounding code. Do not edit files. Return evidence-backed required findings,
optional observations and questions for the orchestrator to record and triage.
```

### Closure prompt

```text
Perform the focused closure review for this workstream. Verify accepted findings and their fixes,
then check only for release-blocking defects introduced by remediation. Update the closure section.
Do not begin another broad review or promote optional observations.
```

## Review command

Use this read-only command for the independent reviews of workstreams 4 through 7 and the initial
whole-feature review. Replace `<prompt>` with the applicable review prompt and task packet:

```bash
claude -p "<prompt>" --model opus --effort medium --permission-mode plan
```

The orchestrator records Claude's evidence under `Required`, `Optional` and `Question`, then owns
triage. Keep closure reviews in the current session because they verify only the accepted finding
list and its fixes.

If the command fails because Claude Code is missing, logged out, out of quota or otherwise cannot
complete the review, assign a fresh reviewer in the current session. Record the substitution in
the workstream or whole-feature review record and continue the same bounded loop.

## External validation gates

Workstream 4 has a macOS writer gate after workstream 6 and before workstream 7. Workstream 4's
reviewed implementation may be accepted before the gate because workstream 6 produces the first
truthful compatible image. After workstream 6 is accepted, push one combined candidate and give
Aidan the commands in the workstream 4 record. Evidence must cover structured disk discovery,
rejection of protected/ineligible-internal/partition targets, target-identity recheck, one successful
spare-card write, image-region readback and boot-only mounting. Start workstream 7 only after the
result and combined candidate hash are recorded.

Workstream 7 has the final MacBook and two-Pi gate. Its candidate must build, provision and boot one
coordinator and one console, exercise failure reporting with a separate disposable card or fixture,
and pass the network, identity, authorization and service checks listed in that record.

A failed attempt enters `Troubleshooting`, not a new implementation-review cycle. Record the
candidate, command, useful output, diagnosis, correction owner and next attempt. Use the original
workstream owner for a focused correction where practical and the original reviewer for a focused
check of changed behavior. Reopen a completed workstream only if evidence invalidates an approved
public contract, architecture, security boundary or previously accepted criterion. Resume normal
orchestration when the gate evidence is `Passed`.

## Final whole-feature review

After every workstream and gate is accepted, run the review command with the task packet in
[final-review.md](final-review.md). The reviewer inspects the complete branch from the recorded
starting commit. The orchestrator triages findings and sends one accepted correction batch to each
original owner. A fresh in-session reviewer performs focused closure. Do not start open-ended
review loops.

## Completion report

Report the delivered commands and behavior, accepted commits, automated checks, both external-gate
records, specification drift, known limitations and deferred optional observations. State plainly
if any external check remains. Do not call the workflow complete while a workstream, gate or final
required finding is unresolved.
