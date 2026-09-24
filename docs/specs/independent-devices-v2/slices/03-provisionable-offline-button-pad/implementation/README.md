# Provisionable offline button pad implementation workflow

Status: draft orchestration instructions.

This directory is the handoff for a fresh agent implementing Slice 03.

## Source of truth

Leads and their agents read the repository instructions, [Slice 03](../../03-provisionable-offline-button-pad.md),
[first device delivery](../../../first-device-delivery.md), [architecture](../../../architecture-and-boundaries.md),
[board reference](../../../../../weact-can485-esp32.md), the accepted
[Slice 02 plan](../../02-simulated-button-pad/implementation/plan.md) and relevant code.
The orchestrator reads only this README, [plan.md](plan.md), and lead returns.
Product documents override this workflow. The request to create it approves use of the Slice 03
draft as the implementation source; this workflow itself remains draft until Aidan approves it.

## Roles and orchestration

The orchestrator owns the integration branch, base, order, leads, escalations to the user, and
completion report. A disposable workstream lead owns its packet through one accepted commit or a
Blocked return. It spawns one implementation agent and uses an independent review command.
Implementation agents own code and their handoff. Reviewers inspect the diff and report evidence
as Required, Optional, or Question. Required means a defect, unmet criterion, boundary violation,
meaningful regression, or unjustified complexity. Optional does not block unless the lead promotes
it. The lead decides findings; reviewers never edit implementation files. Agents do not edit the
shared worktree concurrently.

Read the plan, then spawn the next workstream lead with only its packet path. Read its return only
to decide to continue or stop; it already wrote the plan before committing. After all workstreams
are accepted, spawn the final-review lead. Report to Aidan at workstream acceptance, on escalation,
and at completion. Do not narrate progress otherwise.

A lead returns exactly:

```text
status: Accepted | Blocked
drift: <one line, or none>
escalation: <plan.md escalation id, or none>
```

The lead writes status in the plan table, drift in the decision log, and escalation in the
escalations section before returning. The orchestrator does not transcribe returns. It writes only
the branch and starting commit at the start, and the user's answer in an escalation entry. The
next lead's commit includes those plan edits.

## Agent spawning and review command

This workflow requires delegation, including when run in Codex. On Claude Code, spawn leads and
implementation agents with `Agent`, `subagent_type: general-purpose`,
`run_in_background: false`, and no model override. The call blocks. On Codex, use
`spawn_agent` with `fork_turns: "none"`, no model or reasoning override, and one long
`wait_agent` call per agent. Never busy-poll.

The lead runs independent and closure reviews, and the final-review lead runs the full review,
through this tested read-only command:

```text
claude -p "<review brief>" --model claude-opus-5-5 --effort medium --permission-mode plan
```

The command succeeded on 2026-09-24 without an effort warning. Supply a concrete brief containing
the packet path, base commit and review scope. Capture its output in the assigned review section;
the read-only reviewer cannot write there. If the command fails at execution time, use a fresh
normal subagent for that review and record the substitution. Findings remain evidence for lead
triage.

## Branch and commits

Create `feature/provisionable-offline-button-pad` from the accepted Slice 02 HEAD. If the current
branch contains unrelated or uncommitted work, isolate it without changing that work. Record the
actual branch and starting commit in the plan. Run workstreams sequentially. Keep changes
uncommitted through review and remediation. At acceptance the lead commits code, its packet record
and plan updates once, with a subject naming the workstream. Do not write accepted commit hashes
into documents. Escalate unclear or overlapping ownership.

## Workstream loop

The lead marks `Implementing`, starts a fresh implementation agent, marks `Review` and runs an
independent review, then marks `Remediation` for at most one accepted-finding correction pass.
The original implementation agent revisits and simplifies the affected design instead of layering
wrappers or compatibility paths. The lead marks `Closure review` and uses a fresh review session
with the same configuration and brief, focused on accepted findings and their fixes. Closure is not
another open-ended review. The lead accepts and commits, or records an escalation and returns
Blocked. There is no automatic third loop.

Implementation prompt: read the packet, product sources and accepted dependency handoffs; work
within its ownership; implement every criterion; run targeted checks; remove dead or speculative
code; fill the handoff; leave the diff uncommitted.

Independent review brief: inspect the entire workstream diff against its recorded base and nearby
code, audit every packet criterion and boundary, run proportionate checks, and return verdict plus
Required, Optional, and Question findings with file and evidence. Do not change implementation.

Closure brief: inspect the cumulative diff, the accepted Required findings and their fixes. Check
for remaining release-blocking defects in those fixes, then return a verdict. Do not promote
Optional suggestions or restart general review.

## Interrupted work and external gates

A non-terminal row with no live lead is interrupted. Start a fresh lead for that packet. It audits
the complete diff, base and ownership, verifies the current state, then resumes at the earliest
phase it cannot prove complete. Reuse sound work and rerun undocumented or partial review. Abandon
partial work only if ownership is unclear, the base is wrong, the packet is contradicted, changes
overlap, or repair is less safe than restart. Preserve it in a named stash or recovery branch
first. Escalate unclear ownership instead of overwriting it.

The three hardware gates in the plan need assembled-board evidence. The owning lead records its
candidate, instructions, required evidence and lasting decisions in the packet. For user action
it writes an escalation, sets Blocked, and leaves work uncommitted. The orchestrator asks Aidan
using only that escalation entry, records the answer, then starts a fresh lead. Before resolving
the entry, that lead copies the lasting decision into its handoff and the plan log when later
workstreams need it. Gate troubleshooting is a diagnostic retry loop: record failure, make the
smallest correction, rerun accessible checks and present a new candidate. It does not restart
implementation and review unless behavior, architecture, ownership, security, persistent data,
public contract or an accepted workstream changes. Review meaningful unreviewed changes once
after the gate passes.

## Lead prompts

Workstream lead:

```text
Lead workstream N of the provisionable offline button pad. Read this README, plan.md, and
NN-packet.md, then the source documents named here. The packet is frozen. Run its implementation,
independent review, at most one remediation pass and focused closure yourself. Use the named
Claude review command. Own finding triage and the terminal decision. Run its external gate at
the recorded placement. On acceptance, fill the record, update plan.md and make one workstream
commit. On a user-dependent gate or material product decision, set Blocked, write a concise
escalation with options, recommendation, evidence and unblock condition, and leave work uncommitted.
On interruption, follow the README recovery rules. Return exactly the three lead fields.
```

Final-review lead:

```text
Lead the Slice 03 whole-feature review. Read this README, plan.md and final-review.md, then the
source documents named here. Review the full branch from the recorded starting commit with a fresh
Claude review command. Triage findings; send each accepted correction to a fresh implementation
agent owning those files; run focused closure in a fresh Claude session. Own the terminal decision.
At acceptance fill final-review.md, set the Final row to Accepted and make one commit containing
corrections and records. If blocked, write an escalation, set the Final row to Blocked, leave work
uncommitted and return its id. Return exactly the three lead fields.
```

## Completion report

Report delivered firmware, build and provisioning outcomes, checks run, recorded physical evidence,
pending external checks, specification drift and deferred optional observations. Do not call the
slice complete while a Required finding or hardware gate remains open.
