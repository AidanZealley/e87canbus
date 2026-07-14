# Car frontend implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, material decisions, verification evidence and unresolved issues. It is not a transcript of
commands, a replacement for commit history or permission to claim hardware behavior from software
simulation.

## How to use this log

- Read the roadmap, current phase document, relevant ADRs and all existing entries before starting.
- Append an entry when a phase or meaningful slice is implemented, deliberately deferred or
  blocked.
- Keep entries concise and factual. Link files and tests rather than pasting large code excerpts.
- Do not rewrite earlier entries when a later implementation changes direction; add a correcting
  entry.
- Record departures from the phase specification and why they were necessary.
- Record dependency, generated-route, SQLite migration and public API consequences explicitly.
- Distinguish focused automated tests, repository-wide checks, browser visual checks and physical
  display testing.
- Never claim verified BMW messages, real device health or physical steering safety from this work.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Routing and layouts | Not started | — | TanStack Router, chooser, `/dev` and `/car` shell |
| 2 — Application settings | Not started | — | Revisioned SQLite settings and API |
| 3 — Engine telemetry simulation | Not started | — | RPM/oil/coolant synthetic CAN path |
| 4 — Device health | Not started | — | Explicit simulator status projection |
| 5 — Car UI foundation | Not started | — | Shared data, conversions, warnings and instruments |
| 6 — Car screens | Not started | — | Overview, drive, steering and settings views |
| 7 — Verification and acceptance | Not started | — | Integrated checks and 800x480 browser matrix |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass. Use `Verified` only after every phase
completion criterion and all relevant repository-wide and visual checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The exact phase or smaller slice attempted.
- **Changed:** Important files, contracts, migrations and externally visible behavior.
- **Decisions:** Material implementation choices or deviations, with reasons.
- **Verification:** Exact tests/checks/browser scenarios run and their outcome.
- **Visual/physical checks:** Viewports/themes/states inspected, or explicitly not run.
- **Documentation:** README, API, schema or roadmap documents updated.
- **Dependencies/migrations:** None, or additions and operational/compatibility impact.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact, risk or prerequisite for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-14 — Roadmap specification prepared

- **Status:** Not started
- **Scope:** Converted the approved routed development and car-display plan into assignable phase
  specifications. No application implementation was performed.
- **Changed:** Added the roadmap README, seven phase documents, this durable log and the reusable
  stage-agent prompt under `docs/car-frontend/`.
- **Decisions:** Kept the approved 800x480 target while deliberately omitting a fixed control-size
  rule. Physical touch-control density will be tuned manually after an initial implementation.
  Separated routing, persistence, telemetry, device health, shared UI, screens and integrated
  verification so implementation agents can receive bounded scopes.
- **Verification:** Checked document links, phase sequencing, public contract consistency and
  documentation-only worktree scope. No application tests were required for specification work.
- **Visual/physical checks:** Not applicable; no UI was implemented.
- **Documentation:** All files in this directory are new specification documents.
- **Dependencies/migrations:** None. The documents specify future TanStack Router dependencies and
  a future SQLite migration but do not apply either.
- **Remaining:** Implement Phases 1-7 one bounded phase at a time and record actual results here.
- **Next handoff:** Start with Phase 1, or implement independent backend Phases 2-4 with explicit
  coordination around shared FastAPI composition and snapshot files. Read the current repository
  before treating any suggested file boundary as current truth.

