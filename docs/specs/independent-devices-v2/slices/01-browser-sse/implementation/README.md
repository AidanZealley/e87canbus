# Browser SSE implementation workflow

Status: approved orchestration instructions; execution started 2026-09-16.

This directory is the complete handoff for a fresh orchestration agent implementing Slice 01.

## Source of truth

Read these before starting:

- repository instructions supplied by the execution environment;
- [frontend instructions](../../../../../../frontend/AGENTS.md) for frontend changes;
- [Slice 01](../../01-browser-sse.md);
- [architecture and boundaries](../../../architecture-and-boundaries.md);
- [live and device API](../../../live-and-device-api.md);
- [implementation plan](plan.md); and
- the next numbered workstream packet.

The approved product documents override this workflow. Record any conflict or required product
change in the plan instead of deciding it inside a task packet.

## Roles

The orchestrator owns source interpretation, branch and base tracking, workstream order, review
assignment, finding triage, cross-workstream decisions, final review and completion reporting. It
must resolve overlapping dirty state before an agent starts.

Each implementation agent owns one workstream through one remediation pass. It reads its packet and
accepted handoffs, implements the smallest complete change, runs the named checks, removes obsolete
code, and records its handoff. It does not broaden the approved behavior.

Each reviewer starts with fresh context and uses the Claude command in the assigned packet. The
reviewer reads the worktree but does not edit it. The orchestrator records the returned findings as
Required, Optional or Question. Findings are evidence for the orchestrator to triage.

Agents must not edit the shared worktree concurrently.

## Branch and commit model

Create `feature/browser-sse` from the approved clean HEAD and record that commit in
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
   It revisits the affected design instead of adding compatibility wrappers or special cases.
5. **Closure review.** The original reviewer runs the packet's closure command. It checks accepted
   findings and their fixes for release-blocking defects. It does not start another open review.
6. **Accept and commit.** The orchestrator accepts the workstream or escalates unresolved material
   disagreement. The implementation agent reruns final checks and commits the accepted change.

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
Opus and medium effort. That model, effort and permission combination was verified on 2026-09-16.
The exact prompt and full command appear in each numbered packet and in
[final-review.md](final-review.md). The orchestrator copies Claude's output into the appropriate
record and owns its disposition.

If Claude is unavailable, logged out or out of quota, run that review in a separate fresh agent
session. Record the substitution and continue. Never omit a review because the external command
failed.

## External validation gate

After whole-feature closure and before completion, pause for Aidan to run the accepted branch
locally. Follow the candidate, commands and evidence checklist in
[final-review.md](final-review.md). The gate proves the two applications work in a real browser and
makes the generated-client boundary inspectable.

A failed check stays inside this final validation gate. Record the failing action and evidence,
make the smallest correction, rerun agent-accessible checks, and publish another candidate. Do not
restart implementation and review unless the correction changes approved behavior, architecture,
ownership, security, persistent data or a public contract. The orchestrator decides whether a
meaningful correction needs one focused review before another candidate.

## Final whole-feature review

After all six workstreams are accepted, a new reviewer runs the initial command in
[final-review.md](final-review.md) against the complete branch and recorded starting commit. The
orchestrator assigns accepted corrections to the original workstream owner in one batch. The same
reviewer then runs the focused closure command. There is no automatic third review loop. Aidan's
local validation follows closure.

## Completion report

Report the delivered coordinator and console-host SSE behavior, removed transport and UI code,
verification run, any remaining external checks, specification drift, and deferred Optional
observations. Do not claim completion while a Required finding or acceptance criterion remains open.
