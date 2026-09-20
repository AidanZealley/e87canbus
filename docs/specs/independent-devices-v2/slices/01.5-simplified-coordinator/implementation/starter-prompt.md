Orchestrate the complete implementation of the simplified coordinator.

Read
`docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/README.md`
and `plan.md` beside it. Do not read the specification, task packets, diffs or findings; the
workstream leads own those.

Create `feature/simplified-coordinator` from the current approved clean HEAD and record its base in
the plan.

Then loop: read the plan, spawn a workstream lead for the next workstream passing only its packet
path. The lead records its own status, drift and escalation before committing, so read its return
only to decide whether to continue or stop. Wait for each lead in one blocking call. Do not
busy-poll a running agent.

If a row is in a non-terminal state and has no live lead, start a fresh lead for that workstream and
tell it to recover the uncommitted work using the README's recovery rules.

After the last workstream is accepted, spawn the final-review lead documented in the README.

The leads run reviews through the review command named in the README.

Report to the user at each workstream acceptance, on an escalation, and in the completion report
covering delivered work, verification, external validation pending, and specification drift. Do not
narrate progress otherwise.

When a lead returns Blocked, read only the escalation entry it names in `plan.md`, put that question
to the user, record the answer in the entry, and start a fresh lead for that workstream.

Continue autonomously. Ask only when a lead blocks.

Execute the workflow now rather than restating it.
