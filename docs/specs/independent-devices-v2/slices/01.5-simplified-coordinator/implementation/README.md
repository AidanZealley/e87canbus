# Simplified coordinator implementation workflow

Status: draft orchestration instructions.

This directory is the complete handoff for a fresh orchestration agent implementing Slice 1.5.

## Source of truth

Read these before starting:

- repository instructions supplied by the execution environment;
- [frontend instructions](../../../../../../frontend/AGENTS.md) when a workstream changes frontend code;
- [Slice 1.5](../../01.5-simplified-coordinator.md);
- [ADR 0018](../../../../../decisions/0018-simplify-coordinator-before-independent-devices.md);
- [architecture and boundaries](../../../architecture-and-boundaries.md);
- [live and device API](../../../live-and-device-api.md);
- [first device delivery](../../../first-device-delivery.md);
- ADRs 0001 through 0005, 0008, 0012 and 0017 linked by ADR 0018;
- [implementation plan](plan.md); and
- the next numbered workstream packet.

The product documents override this workflow. Do not preserve a behavior merely because an older
ADR or test describes it. Record any other conflict or required product change in the plan.

## Roles

The orchestrator owns source interpretation, branch and base tracking, workstream order, agent
assignment, finding triage, cross-workstream decisions, final review and completion reporting. It
must resolve overlapping dirty state before an agent starts.

Each implementation agent owns one workstream through one remediation pass. It reads its packet and
accepted handoffs, implements the smallest complete change, runs the named checks, performs a
deletion and simplification pass, and records its handoff. It does not broaden the approved behavior.

Each reviewer starts with fresh context and uses the Claude command in the assigned packet. The
reviewer reads the worktree but does not edit it. The orchestrator records every finding as Required,
Optional or Question and owns its disposition.

Agents must not edit the shared worktree concurrently.

## Branch and commit model

Create `feature/simplified-coordinator` from the approved clean HEAD and record that commit in
[plan.md](plan.md). Run workstreams sequentially.

Keep each implementation diff uncommitted through implementation, independent review, remediation
and closure review. After acceptance, the implementation agent creates one coherent implementation
commit. The orchestrator records its hash in a separate bookkeeping commit, then starts the next
workstream from that clean head.

Do not include unrelated pre-existing changes in a workstream commit.

## Per-workstream loop

1. **Start.** Confirm the dependency is accepted, assign one implementation agent, record the base,
   and mark the packet `Implementing`.
2. **Implementation handoff.** The agent implements the packet, runs targeted checks, performs a
   deletion and simplification pass, and fills in its handoff.
3. **Independent review.** A fresh reviewer runs the packet's exact Claude command against the
   uncommitted diff. The orchestrator records and triages every finding.
4. **Remediation.** The original implementation agent gets one batch of accepted Required findings.
   It revisits the affected design instead of adding wrappers, flags or compatibility paths.
5. **Closure review.** The original reviewer runs the packet's closure command. It checks accepted
   findings and their fixes for release-blocking defects. It does not start another open review.
6. **Accept and commit.** The orchestrator accepts the workstream or resolves material disagreement.
   The implementation agent reruns final checks and commits the accepted change.

Use this implementation prompt, followed by the task packet path:

```text
Implement this workstream from its recorded base. Read the source-of-truth documents and accepted
dependency handoffs first. Stay within initial ownership unless the packet permits an integration
exception. Meet every acceptance criterion, run the targeted checks, perform a deletion and
simplification pass, and complete the implementation handoff. Leave changes uncommitted for review.
```

Use the exact independent and closure commands recorded in each packet. Do not resume a Claude
session for closure. A fresh call must read the recorded findings and current cumulative diff.

## Review command

Every independent, closure and whole-feature review uses Claude Code in read-only plan mode with
Opus and medium effort. The exact combination was verified on 2026-09-18. The full command appears
in each numbered packet and [final-review.md](final-review.md).

If Claude is unavailable, logged out or out of quota, run that review in a separate fresh agent
session. Record the substitution and continue. Never omit a review because the external command
failed.

## Final whole-feature review

After all five workstreams are accepted, a new reviewer runs the initial command in
[final-review.md](final-review.md) against the complete branch and recorded starting commit. The
orchestrator assigns accepted corrections to the original owner in one batch. The same reviewer then
runs the focused closure command. There is no automatic third review loop.

All acceptance criteria are repository-testable. This slice has no hardware or vehicle validation
gate because it removes unverified output rather than adding one.

## Completion report

Report deleted behavior and machinery, the retained coordinator responsibilities, verification run,
specification drift and deferred Optional observations. Do not claim completion while a Required
finding or acceptance criterion remains open.
