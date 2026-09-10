# Starter prompt

```text
Orchestrate the complete implementation of device lifecycle tooling.

Begin by reading docs/specs/device-provisioning/implementation/README.md and every source-of-truth
document it identifies. Treat those documents as the approved requirements and workflow.

Create feature/device-lifecycle-tooling from the current approved HEAD and record its base in the
plan. Execute every workstream through the documented workflow. Use a fresh implementation agent
for each workstream and a different fresh agent for independent review. Keep review loops bounded,
maintain the records and commit only accepted work.

Pause at each documented external validation gate. Treat failed attempts as troubleshooting inside
the owning workstream, not as new implementation and review cycles, unless the documented reopening
conditions apply. Resume autonomous execution when the gate's evidence requirement is satisfied.

After all workstreams and gates are accepted, run the documented whole-feature review. Triage
findings, return accepted corrections to their implementation owners, complete focused closure and
run final verification.

Prioritize the smallest complete implementation and preserve all non-goals and security boundaries.
Continue autonomously. Ask only if a decision materially changes approved behavior or architecture.

Report delivered work, verification, external validation pending and specification drift. Execute
the workflow rather than stopping after restating it.
```
