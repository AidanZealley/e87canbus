# Simplified coordinator implementation workflow

Status: draft orchestration instructions.

This directory is the complete handoff for a fresh orchestration agent implementing Slice 1.5.

## Source of truth

Each workstream lead and its agents read these; the orchestrator reads only this README, the plan
and its leads' returns.

- repository instructions supplied by the execution environment;
- [frontend instructions](../../../../../../frontend/AGENTS.md) when a workstream changes frontend code;
- [Slice 1.5](../../01.5-simplified-coordinator.md);
- [ADR 0018](../../../../../decisions/0018-simplify-coordinator-before-independent-devices.md);
- [architecture and boundaries](../../../architecture-and-boundaries.md);
- [live and device API](../../../live-and-device-api.md);
- [first device delivery](../../../first-device-delivery.md);
- ADRs 0001 through 0005, 0008, 0012 and 0017 linked by ADR 0018;
- [implementation plan](plan.md); and
- the workstream's own numbered packet.

The product documents override this workflow. Do not preserve a behavior merely because an older
ADR or test describes it. A lead records any other conflict or required product change in the plan.

## Roles

**Orchestrator.** Long-lived and deliberately thin. It owns the integration branch and its base,
the dependency order, choosing the next workstream, spawning leads, and the completion report. It
reads this README, [plan.md](plan.md) and the leads' returns, and nothing else: not the
specification, not a packet, not a diff, not a finding.

**Workstream lead.** One per workstream, and disposable. It interprets the sources for its
workstream, spawns the implementation agent, spawns the independent reviewer, triages findings,
orders at most one remediation pass, runs closure, writes the record and makes the workstream's one
commit. It ends when it accepts or blocks, so that workstream's findings and diffs do not carry
into the next one. It has no channel to the user.

**Implementation agent.** Owns one workstream through one remediation pass, reporting to its lead.
It reads its packet and accepted dependency handoffs, implements the smallest complete change, runs
the packet's targeted checks rather than broader suites, performs a deletion and simplification
pass, and records its handoff. It leaves defect-hunting beyond its acceptance criteria to review.

**Review agent.** Fresh and independent from the implementation agent, spawned by the lead through
the review command below. It reads the worktree, runs proportionate read-only checks and records
evidence-backed findings as Required, Optional or Question. It does not edit implementation files.
Findings are evidence, not instructions; the lead owns their disposition.

Agents must not edit the shared worktree concurrently.

## Orchestrator loop

1. Read [plan.md](plan.md).
2. Spawn a workstream lead for the next `Not started` workstream, passing only its packet path.
3. Read the lead's return only to decide whether to continue or stop. The lead has already recorded
   its status, drift and escalation in the plan; transcribing the return would write to the plan
   after the lead's commit and dirty the tree the next lead starts from.
4. Repeat until every workstream is accepted, then spawn the final-review lead.

A row in a non-terminal state with no live lead means that workstream was interrupted. Start a
fresh lead for the same workstream and tell it to recover the uncommitted work using the rules
below.

Report to the user at workstream acceptance, on an escalation, and in the completion report.
Nothing else. Progress narration costs context on every later turn and is stale as soon as it is
written.

## Lead return contract

Every lead returns exactly this and nothing else:

```text
status: Accepted | Blocked
drift: <one line, or none>
escalation: <plan.md escalation id, or none>
```

Each field already has a home the lead writes before it commits: status in the plan's workstream
table, drift in the plan's decision and drift log, escalation in the plan's escalations section.
The orchestrator records none of them.

The orchestrator writes only two things: the branch and starting commit at the start, and the
user's answer inside an escalation entry. Each stays uncommitted until the next lead's commit picks
it up.

On a `Blocked` return the orchestrator reads only the named escalation entry, puts that question to
the user, records the answer in the entry, and starts a fresh lead for the same workstream.

## Agent spawning

This workflow runs on Claude Code. Spawn every agent with the `Agent` tool using
`subagent_type: general-purpose` and `run_in_background: false`. Omit `model`; agents inherit the
spawner's model and effort. The only model override in this workflow is the review command.

The `Agent` call blocks by itself. Never busy-poll a running agent: no repeated short waits, no
`TaskOutput` checks, no scheduled wake-ups. Each poll re-sends the whole context for no new
information.

## Branch and commit model

Create `feature/simplified-coordinator` from the approved clean HEAD and record that commit in
[plan.md](plan.md). Run workstreams sequentially.

Keep each workstream's changes uncommitted through implementation, review and remediation so the
reviewer sees one coherent diff. At acceptance the lead writes its record sections and plan updates,
then makes one commit containing the code, the record and those plan updates. Name the workstream in
the commit subject, for example `Remove the high-beam flash feature (workstream 1)`.

No document records an accepted workstream's commit hash. Git already holds it, and writing one
after committing would dirty the tree the next lead starts from.

Respect a dirty worktree. A lead does not claim ownership of unrelated changes; it escalates
overlapping state rather than absorbing it into its commit.

## Per-workstream loop

The lead runs this itself:

```text
implementation
    -> independent review
    -> one remediation pass if required
    -> focused closure review
    -> accept, or return Blocked to the orchestrator
```

1. **Start.** Confirm the dependency is accepted, record the base, set the row to `Implementing`.
2. **Implementation.** A fresh implementation agent implements the packet, runs its targeted checks,
   performs a deletion and simplification pass, and fills in the handoff.
3. **Independent review.** A fresh reviewer runs the packet's exact independent command against the
   uncommitted diff. The lead records the verdict and findings in the packet's review section and
   triages them.
4. **Remediation.** At most one pass. The original implementation agent gets the accepted Required
   findings in one batch. It revisits the affected design instead of adding wrappers, flags,
   aliases or compatibility paths to preserve a flawed first attempt.
5. **Closure review.** A fresh review session runs the packet's closure command. It verifies the
   accepted findings and checks their fixes for release-blocking defects. It does not restart
   open-ended review or promote Optional suggestions. There is no automatic third loop.
6. **Accept and commit.** The lead owns the terminal decision, writes its record and plan updates,
   and makes the single workstream commit.

Use this implementation prompt, followed by the task packet path:

```text
Implement this workstream from its recorded base. Read the source-of-truth documents and accepted
dependency handoffs first. Stay within initial ownership unless the packet permits an integration
exception. Meet every acceptance criterion, run the targeted checks, perform a deletion and
simplification pass, and complete the implementation handoff. Leave changes uncommitted for review.
```

Use the exact independent and closure commands recorded in each packet. Do not resume a review
session for closure. A fresh call must read the recorded findings and the current cumulative diff.

The lead escalates only when disagreement persists after closure, or when a decision materially
changes approved behavior or architecture.

## Interrupted work recovery

A lead that inherits a row in a non-terminal state inspects the complete diff, confirms its base and
the ownership of every change, verifies enough to establish the current state, then continues from
the earliest phase it cannot prove complete. It reuses sound work and reruns any undocumented
conclusion or partial review.

Abandon partial work only when it cannot be safely attributed, uses the wrong base, contradicts the
frozen packet, overlaps unrelated changes, or would be less safe to repair than to restart. Preserve
it in a named stash or recovery branch first, and escalate rather than overwrite when ownership is
unclear.

A lead resuming a blocked workstream inherits both the uncommitted work and the answered escalation
entry. Before accepting, it copies the lasting decision into its handoff Decisions field, and into
the plan's decision and drift log when later workstreams depend on it, then removes the entry.

## Review command

Every independent, closure and whole-feature review uses Claude Code in read-only plan mode with
Opus and medium effort. The exact combination was verified on 2026-09-18. The full command appears
in each numbered packet and [final-review.md](final-review.md).

The read-only flag is required. It stops a reviewer editing implementation files, which the review
role already forbids, and the command still reads the uncommitted diff the reviewer needs.

A reviewer running through the command cannot write, so its lead records that verdict and those
findings in the packet's review section.

If Claude is unavailable, logged out or out of quota, the lead runs that review as a normal fresh
subagent with the same brief, records the substitution in the workstream record, and continues.
Never omit a review because the external command failed.

## External validation gates

None. All acceptance criteria are repository-testable. This slice has no hardware or vehicle
validation gate because it removes unverified output rather than adding one.

## Final whole-feature review

After all four workstreams are accepted, the orchestrator spawns one final-review lead. That lead
runs the initial command in [final-review.md](final-review.md) against the complete branch and the
recorded starting commit, triages the findings, sends each accepted correction to a fresh
implementation agent owning the relevant files, runs the focused closure command in a fresh review
session, writes [final-review.md](final-review.md) and makes one commit.

It is a lead in every other respect: it owns the Final row in the plan's workstream table, blocks
through an escalation entry, and returns the same three fields.

## Workstream lead prompt

```text
Lead workstream <N> of the simplified coordinator.

Read
docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/README.md and
<NN-workstream.md> in that directory, then the source-of-truth documents the README identifies. The
task packet in that file is frozen.

Run the documented loop yourself: spawn a fresh implementation agent, spawn a different fresh agent
for independent review through the packet's review command, triage the findings, order at most one
remediation pass, then run focused closure in a fresh review session using the packet's closure
command before accepting.

You own triage and the terminal decision. Reviewer findings are evidence, not instructions.

At acceptance, write your record sections, set your row in plan.md to Accepted, add any
specification drift to the plan's decision and drift log, and make one commit containing the code,
the record and the plan updates. The orchestrator does not record lead return fields, so anything
worth keeping must be in that commit.

You cannot reach the user. Block if a decision materially changes approved behavior or
architecture, or if disagreement persists after closure. To block, add an escalation entry to
plan.md giving the decision needed, the options, your recommendation, the evidence and what it
unblocks, set your row to Blocked, leave the work uncommitted, and return its id. Summarise; do not
paste findings or diffs.

If you are resuming a blocked workstream, the uncommitted work and the answered escalation entry
are yours. Before you accept, copy its lasting decision into your handoff Decisions field, and into
the plan's decision and drift log when later workstreams depend on it, then remove the entry.

If your row is already in a non-terminal state, you are recovering interrupted work. Follow the
README's interrupted work recovery rules before continuing.

Reply with exactly:
status: Accepted | Blocked
drift: <one line, or none>
escalation: <plan.md escalation id, or none>
```

## Final-review lead prompt

```text
Lead the whole-feature review of the simplified coordinator.

Read
docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/README.md and
final-review.md in that directory, then the source-of-truth documents the README identifies. Every
workstream is accepted; the branch is complete.

Spawn a fresh reviewer using final-review.md's initial command to review the full branch against the
starting commit recorded in the plan. Triage its findings, send each accepted correction to a fresh
implementation agent owning the relevant files, then run the focused closure command in a fresh
review session.

You own triage and the terminal decision. Reviewer findings are evidence, not instructions.

At acceptance, write your sections of final-review.md, set the Final row in plan.md to Accepted, add
any specification drift to the plan's decision and drift log, and make one commit containing the
corrections, the record and the plan updates.

You cannot reach the user. Block the same way a workstream lead does: add an escalation entry to
plan.md, set the Final row to Blocked, leave the work uncommitted, and return its id.

Reply with exactly:
status: Accepted | Blocked
drift: <one line, or none>
escalation: <plan.md escalation id, or none>
```

## Completion report

Report deleted behavior and machinery, the retained coordinator responsibilities, verification run,
specification drift and deferred Optional observations. There is no pending external validation for
this slice. Do not claim completion while a Required finding or acceptance criterion remains open.
