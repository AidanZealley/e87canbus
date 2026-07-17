# ISO-TP/RGB button-pad phase agent prompt

[Overview](README.md) · [Implementation log](implementation-log.md)

Give an agent one phase only: `1` for
[Transport foundation](phase-1-transport-foundation.md), or `2` for
[RGB virtual button pad](phase-2-rgb-virtual-button-pad.md).

```text
Implement phase <PHASE_NUMBER> of docs/isotp-rgb-button-pad.

Before changing anything:

1. Read the overview, this prompt, the complete implementation log, and the
   selected phase document. The overview and phase document own all feature
   and protocol decisions; do not infer additional work from their titles.
2. Read every applicable AGENTS.md file, inspect git status, and inspect the
   current implementation. Preserve unrelated user changes.
3. Confirm each prerequisite phase is marked Completed. If not, report the
   dependency instead of bypassing it.

Implementation discipline:

4. Implement only the selected phase and the smallest compatibility/coherence
   fixes it requires. Do not start later-phase product work.
5. Prefer modifying, simplifying, or deleting existing code over adding new
   modules, wrappers, models, configuration, aliases, compatibility paths, or
   generic frameworks. Add a boundary only when it creates a concrete ownership
   or validation guarantee required by the phase.
6. Keep one canonical path and one source of truth. Do not retain replaced
   behavior merely because changing in-repository callers is inconvenient.
7. Do not add speculative flexibility for future devices, protocols, UI,
   effects, configuration, or error handling. Keep code and tests proportionate
   to the exact contract in the selected phase.
8. Preserve existing safety boundaries. Do not weaken TX authorization,
   collision-validation requirements, hardware evidence gates, or bench/in-car
   warnings.
9. Use real encoded frames and normal product boundaries in simulations. Do
   not shortcut a product path by directly forcing state.
10. Update generated artifacts through their source and generator, never as
    unrelated hand edits.

Before finishing:

11. Run every check required by the selected phase and proportionate
    regressions. Do not hide, skip, or reinterpret failures.
12. Inspect the complete diff and diff statistics. Remove superseded code and
    unnecessary structure; record any substantial unavoidable complexity and
    why its boundary is required.
13. Update the implementation log in the same change: status, exact commands
    and results, important decisions/deviations, limitations, and follow-up.
    Mark a phase Completed only when its required checks pass; otherwise mark
    it Blocked with the concrete blocker and current repository state.

Finish with a concise handoff: outcome, verification, limitations, and log
update. Never claim physical readiness from compilation or simulation.
```
