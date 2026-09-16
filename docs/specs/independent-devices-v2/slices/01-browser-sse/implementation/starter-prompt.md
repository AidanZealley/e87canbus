Orchestrate the complete implementation of the browser SSE migration.

Begin by reading
`docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/README.md` and every
source-of-truth document it identifies. Treat those documents as the approved requirements and
workflow.

Create `feature/browser-sse` from the current approved HEAD and record its base in the plan.

Execute every workstream through the documented workflow. Use a fresh implementation agent for each
workstream and a different fresh agent for independent review. Keep review loops bounded, maintain
the records, and commit only accepted work.

Run every review through the review command named in the relevant workflow packet, exactly as
documented. Treat its findings as evidence and triage them yourself. If a review call fails, run
that review in a separate fresh session, record the substitution, and continue.

After all workstreams are accepted, run the documented whole-feature review. Triage findings and
return accepted corrections to their implementation owners. Complete focused closure and final
verification.

Pause at the documented local browser validation gate. Treat failed attempts as troubleshooting
inside the gate, not as new implementation and review cycles, unless the documented reopening
conditions apply. Resume autonomous completion after Aidan supplies the required evidence.

Prioritize the smallest complete implementation and preserve all non-goals and boundaries. Continue
autonomously. Ask only if a decision materially changes approved behavior or architecture.

Report delivered work, verification, external validation pending and specification drift. Execute
the workflow rather than stopping after restating it.
