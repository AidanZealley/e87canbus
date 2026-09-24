# Starter prompt

```text
Orchestrate the complete Slice 03 provisionable offline button pad implementation.

Read docs/specs/independent-devices-v2/slices/03-provisionable-offline-button-pad/implementation/README.md
and plan.md. Do not read specifications, task packets, diffs or findings; leads own those.

Create feature/provisionable-offline-button-pad from the approved Slice 02 HEAD and record the
actual branch and starting commit in the plan. If that branch or unrelated work already exists,
preserve it and choose a safe isolated base. Then read the plan and spawn a lead for the next
workstream, passing only its packet path. Wait in one blocking call. Read its three-field return
only to decide to continue or stop; the lead writes the plan before committing. Do not transcribe
the return.

Delegate as the README requires. In Codex use fork_turns "none" and no model or
reasoning_effort override for spawned agents. Never busy-poll. Leads run independent and closure
reviews using the README's Claude Opus 5.5 medium read-only command.

If a non-terminal row has no live lead, start a fresh lead for its packet and have it audit and
resume the uncommitted work. If a lead returns Blocked, read only its escalation entry in the
plan, ask Aidan for the needed decision or hardware evidence, record the answer there, then
start a fresh lead. Hardware gates use the same path.

After all three workstreams are accepted, spawn the final-review lead. Report only at each
workstream acceptance, on an escalation, and at completion. The final report covers delivered
work, verification, physical evidence, remaining external checks and specification drift.
Continue autonomously. Execute the workflow now.
```
