# Assistance curve implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, important decisions, verification evidence and unresolved issues. It is not a transcript
of commands or a replacement for commit history.

## How to use this log

- Read the roadmap, current phase document, relevant ADRs and all earlier entries before starting.
- Append an entry when a phase or meaningful slice is completed, deliberately deferred or blocked.
- Keep entries concise and factual. Link files and tests instead of pasting large code excerpts.
- Do not rewrite earlier entries to make later decisions look inevitable. Add a correcting entry.
- Record deviations from the phase document and why they were necessary.
- Record new dependencies, migrations and compatibility consequences explicitly.
- Never claim physical validation from simulator or software-only results.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Profile domain model | Not started | — | — |
| 2 — SQLite persistence | Not started | — | — |
| 3 — Runtime activation | Not started | — | — |
| 4 — Profile API | Not started | — | — |
| 5 — Interactive editor | Not started | — | — |
| 6 — Smooth interpolation | Not started | — | — |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass; use `Verified` only after every phase
completion criterion and the relevant repository-wide checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The slice of the phase attempted.
- **Changed:** Important files and externally visible behavior.
- **Decisions:** Material choices or deviations, with reasons.
- **Verification:** Exact tests/checks run and their outcome.
- **Documentation:** README/design/API documents updated.
- **Dependencies/migrations:** None, or list additions and operational impact.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-14 — Version-1 fixed speed grid selected

- **Status:** Not started
- **Scope:** Resolved the blocking product input for Phase 1; no implementation code was changed.
- **Changed:** Defined eight fixed points at `0, 10, 20, 30, 60, 100, 160, and 250 km/h` and the
  built-in per-mille values derived from the current curve.
- **Decisions:** Point X positions are immutable in schema version 1. The grid is denser at low
  speeds, retains the current `30` and `100 km/h` breakpoints, and exposes two high-speed controls.
  The `250 km/h` endpoint is an editor-domain choice, not a hardware claim.
- **Verification:** Recalculated the current piecewise-linear values at every selected speed and
  checked the documentation with `git diff --check`.
- **Documentation:** Updated the roadmap and Phase 1 domain-model contract.
- **Dependencies/migrations:** None; changing this grid after profiles exist will require a new
  schema version or explicit migration.
- **Remaining:** All six implementation phases.
- **Next handoff:** Phase 1 can begin by encoding the documented grid, integer values and validation
  without another product decision.

### 2026-07-14 — Roadmap prepared

- **Status:** Not started
- **Scope:** Planning only; no curve implementation code was changed.
- **Changed:** Added phased plans for the profile model, SQLite persistence, runtime activation,
  API, editor and smooth interpolation, plus Proposed ADR 0007.
- **Decisions:** Draft, active and saved state remain distinct. The first editor release uses honest
  linear interpolation. Controller synchronization remains outside these phases.
- **Verification:** Documentation links and `git diff --check` reviewed.
- **Documentation:** This directory and the ADR index.
- **Dependencies/migrations:** None.
- **Remaining:** All six implementation phases.
- **Next handoff:** Superseded by the later grid-selection entry above.
