# Simulated independent button pad implementation workflow

Status: draft orchestration instructions.

This directory is the complete handoff for a fresh orchestration agent implementing Slice 02.

## Source of truth

Read these before starting:

- repository instructions supplied by the execution environment;
- [frontend instructions](../../../../../../frontend/AGENTS.md) for generated client changes;
- [Slice 02](../../02-simulated-button-pad.md), approved by the request that created this workflow;
- [architecture and boundaries](../../../architecture-and-boundaries.md);
- [live and device API](../../../live-and-device-api.md);
- [first device delivery](../../../first-device-delivery.md);
- [Slice 1.5](../../01.5-simplified-coordinator.md) and its accepted implementation handoff;
- [ADR 0018](../../../../../decisions/0018-simplify-coordinator-before-independent-devices.md);
- [ADR 0017](../../../../../decisions/0017-browser-live-state-over-sse.md);
- [ADR 0001](../../../../../decisions/0001-single-owner-event-kernel.md);
- [ADR 0003](../../../../../decisions/0003-production-path-simulation.md);
- [ADR 0013](../../../../../decisions/0013-provisioned-wifi-device-network.md);
- [ADR 0015](../../../../../decisions/0015-offline-device-provisioning.md);
- [implementation plan](plan.md); and
- the next numbered workstream packet.

The approved product documents and Aidan's recorded 2026-09-18 direction override this workflow.
Slice 1.5 is a required clean starting boundary: it removes coordinator-device CAN, the device
registry, legacy firmware and the old effect system before this workflow begins. Do not repeat that
cleanup or restore compatibility with it. Record any other conflict or required product change in
the plan instead of deciding it inside a task packet.

## Roles

The orchestrator owns source interpretation, branch and base tracking, workstream order, review
assignment, finding triage, cross-workstream decisions, final review and completion reporting. It
must resolve overlapping dirty state before an agent starts.

Each implementation agent owns one workstream through one remediation pass. It reads its packet and
accepted handoffs, implements the smallest complete change, runs the named checks, removes obsolete
or speculative machinery, and records its handoff. It does not broaden the approved behavior.

Each reviewer starts with fresh context and uses the Claude command in the assigned packet. The
reviewer reads the worktree but does not edit it. The orchestrator records the returned findings as
Required, Optional or Question and owns their disposition.

Agents must not edit the shared worktree concurrently.

## Branch and commit model

Create `feature/simulated-button-pad` from the approved clean HEAD containing completed Slice 1.5 and
record that commit in [plan.md](plan.md). Run workstreams sequentially.

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
   It revisits the affected design instead of adding compatibility wrappers, flags or special cases.
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
Opus and medium effort, continuing the accepted Slice 01 review convention. That exact combination
was verified on 2026-09-18. The full command appears in each numbered packet and in
[final-review.md](final-review.md).

If Claude is unavailable, logged out or out of quota, run that review in a separate fresh agent
session. Record the substitution and continue. Never omit a review because the external command
failed.

## Final whole-feature review

After all seven workstreams are accepted, a new reviewer runs the initial command in
[final-review.md](final-review.md) against the complete branch and recorded starting commit. The
orchestrator assigns accepted corrections to the original workstream owner in one batch. The same
reviewer then runs the focused closure command. There is no automatic third review loop.

All Slice 02 acceptance criteria are testable in the repository. Do not add a browser, hardware,
nginx TLS or Wi-Fi validation gate to this workflow. Those boundaries are explicitly outside this
simulated slice.

## Completion report

Report the delivered identity, device contract, persistence, production routes, configuration
stream and simulated client; verification run; specification drift; and deferred Optional
observations. Do not claim completion while a Required finding or acceptance criterion remains open.
