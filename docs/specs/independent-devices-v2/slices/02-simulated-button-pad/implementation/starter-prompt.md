Orchestrate the complete implementation of the simulated independent button pad.

Begin by reading
`docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/README.md`
and every source-of-truth document it identifies. Treat those documents as the approved requirements
and workflow.

Create `feature/simulated-button-pad` from the current approved clean HEAD and record its base in the
plan. Execute every workstream sequentially through the documented implementation, independent
review, bounded remediation, closure and acceptance loop. Use a fresh implementation agent for each
workstream and a different fresh reviewer. Maintain the durable records and commit only accepted
work.

Run every review through the exact Claude Opus medium command in its packet. Treat findings as
evidence and triage them yourself. If the command fails, use the documented fresh-session fallback
and record the substitution.

After all workstreams are accepted, run the documented whole-feature review and final verification.
Prioritize the smallest complete implementation, preserve the clean Slice 1.5 boundary and vehicle
CAN, and add no generic device framework. Continue autonomously. Ask only if a decision materially
changes approved behavior or architecture.

Report delivered work, verification, specification drift and deferred Optional observations.
Execute the workflow rather than stopping after restating it.
