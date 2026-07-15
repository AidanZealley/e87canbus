# Unified controller reduction implementation log

This is the durable handoff for the deletion-led simplification pass. It records measured reduction,
behavior preserved and any target that could not be met safely. It must not count moved, generated
or reformatted code as simplification.

## Phase status

| Phase | Status | Last entry | Production reduction | Notes |
|---:|---|---|---:|---|
| 1 — Baseline and deletion map | Not started | — | — | Measure current tree and approve the deletion ledger |
| 2 — Contract/model consolidation | Not started | — | — | Remove parallel representations and adapters |
| 3 — Runtime/service reduction | Not started | — | — | Shorten the single-owner path |
| 4 — Publication/diagnostics reduction | Not started | — | — | Preserve bounds with fewer mechanisms |
| 5 — Composition/frontend seams | Not started | — | — | Remove construction and consumption layers |
| 6 — Test-suite reduction | Not started | — | — | Remove implementation archaeology and redundant tests |
| 7 — Cutover/acceptance | Not started | — | — | Prove overall reduction and behavior |

## Current handoff

Start Phase 1 from the verified unified-controller tree. Reproduce the current production/test/doc/
generated counts, inventory named concepts and map the common flows before changing production
code. Treat the 1,000-line overall production target as provisional until the deletion ledger is
reviewed, but do not lower it merely because deletion is inconvenient. Preserve the user's newer
work and the existing no-facade, bounded-publication and deny-by-default safety outcomes.

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
`Implemented` requires a measurable simplification and focused checks. `Verified` requires all
phase criteria, repository-wide checks relevant to the change and honest before/after accounting.

## Entry template

Add entries newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** Exact slice attempted and behavior intentionally left unchanged.
- **Deletion hypothesis:** Concepts/layers/files expected to disappear and why they are redundant.
- **Production accounting:** Base commit; backend/frontend lines added/deleted/net; files added,
  deleted and touched. Report tests/docs/generated separately.
- **Cognitive accounting:** Named concepts, flow hops and contract copies before/after.
- **Changed:** Important deletions, necessary additions and public-contract consequences.
- **Protected behavior:** Bounds, ownership, reconnect, safety and failure behavior re-proved.
- **Tests:** Retained contract tests; tests removed with deleted internals; new tests and why needed.
- **Test accounting:** Test files/lines/count/runtime before/after; value classifications retained;
  obsolete/private/impossible-state tests removed.
- **Verification:** Exact focused and repository-wide commands, counts, warnings and failures.
- **Browser/soak/physical checks:** Evidence run, prior evidence still applicable, or honestly not run.
- **Dependencies/migrations:** None, removals, or additions with justification.
- **Compatibility/removal:** Facades/aliases removed; none may be introduced silently.
- **Target variance:** Budget met, exceeded or blocked; explain variance without cosmetic accounting.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** Most important deletion opportunity, risk or prerequisite.
```

## Entries

None yet.
