# Orchestration starter prompt

Status: ready to use after these approved documents are committed and the worktree is clean.

Start a fresh orchestration thread in this repository and paste the prompt below. The prompt is
short by design: the linked documents are the source of truth and should not be duplicated in the
thread instructions.

```text
Orchestrate the complete implementation of the minimal coordinator panel.

Begin by reading docs/coordinator-panel/implementation/README.md and every source-of-truth document
it identifies. Treat those documents as the approved requirements and workflow.

Create a new implementation branch named feature/coordinator-panel-implementation from the current
approved HEAD and record its base in the implementation plan.

Execute every workstream through the documented workflow. Use a fresh implementation agent for
each workstream and a different fresh agent for its independent review. Keep each review loop
bounded as specified, maintain the workstream records and plan, and commit only accepted work.

After all workstreams are accepted, assign a fresh agent to perform the documented whole-feature
review. Triage its findings yourself and return accepted corrections to the relevant implementation
owners. Complete the focused closure review and final verification.

Prioritise the smallest complete implementation and preserve all stated non-goals and module
boundaries. Continue autonomously through completion. Ask me only if a decision would materially
change the approved product behaviour or architecture.

At the end, report what was completed, verification performed, hardware validation still pending,
and any specification drift.
```

Suggested thread title: `Coordinator panel implementation orchestration`.

The orchestration agent should execute the workflow rather than stop after restating or approving
the plan.
