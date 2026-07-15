# Unified controller implementation log

This is the durable handoff record for the phased work in this directory. It records what actually
changed, material decisions, verification evidence and unresolved issues. It is not a transcript of
commands, a replacement for commit history or permission to claim hardware behavior from software
simulation.

## How to use this log

- Read the roadmap, current phase document, applicable ADRs and all existing entries before work.
- Append an entry when a phase or meaningful slice is implemented, deliberately deferred or
  blocked.
- Keep entries concise and factual. Link files and tests instead of pasting large code excerpts.
- Add new entries newest first. Do not rewrite history when later work changes direction.
- Record departures from the phase specification and why they were necessary.
- Record dependency, lockfile, generated-contract, SQLite migration and public API consequences.
- Distinguish focused tests, repository-wide checks, browser checks, soak tests and physical/CAN
  evidence.
- State whether real CAN TX was available and enabled. Never imply physical output from simulation.
- Record compatibility paths introduced and the exact later phase responsible for removing them.

## Phase status

| Phase | Status | Last entry | Notes |
|---:|---|---|---|
| 1 — Runtime contracts | Not started | — | Architecture record, contracts and regression baseline |
| 2 — Unified composition | Not started | — | One controller/API lifecycle with selected adapters |
| 3 — Commands and resources | Not started | — | Semantic commands and precise durable resources |
| 4 — Socket.IO publication | Not started | — | Fixed topics, reconnect snapshot and bounded delivery |
| 5 — Frontend data ownership | Not started | — | Zustand live state and TanStack Query HTTP ownership |
| 6 — Simulation/device convergence | Not started | — | Physical, emulated and observer pathways |
| 7 — Reliability/deployment | Not started | — | Failure policy, health, shutdown and service operation |
| 8 — Cutover/acceptance | Not started | — | Legacy removal, integrated checks and soak evidence |

Allowed status values are `Not started`, `In progress`, `Blocked`, `Implemented`, and `Verified`.
Use `Implemented` when code exists and focused checks pass. Use `Verified` only when every phase
completion criterion and all relevant repository-wide, browser, soak and adapter checks pass.

## Entry template

Copy this section to the top of **Entries**, newest first:

```markdown
### YYYY-MM-DD — Phase N: short outcome

- **Status:** In progress | Blocked | Implemented | Verified
- **Scope:** The exact phase or smaller slice attempted.
- **Changed:** Important files, contracts, migrations and externally visible behavior.
- **Decisions:** Material implementation choices or deviations, with reasons.
- **Verification:** Exact focused and repository-wide checks run and their outcome.
- **Browser/soak/physical checks:** Scenarios, duration and observations, or explicitly not run.
- **Documentation:** README, ADR, API, schema or operator documents updated.
- **Dependencies/migrations:** None, or additions and operational/compatibility impact.
- **Compatibility/removal:** Temporary compatibility retained and its removal owner, or none.
- **Remaining:** Concrete work left in this phase.
- **Next handoff:** The most useful fact, risk or prerequisite for the next implementer.
```

Omit no field; write `None` when it genuinely does not apply.

## Entries

### 2026-07-15 — Roadmap specification prepared

- **Status:** Not started
- **Scope:** Converted the approved unified controller, Socket.IO, Zustand/TanStack Query and
  production-path simulation architecture into assignable phase specifications. No application
  implementation was performed.
- **Changed:** Added the roadmap README, eight phase documents, this implementation log and the
  reusable phase-agent prompt under `docs/unified-controller/`.
- **Decisions:** Kept one modular process and one state owner; separated backend composition,
  commands, publication, frontend ownership, simulation convergence, reliability and cutover so
  each agent receives a bounded outcome. Compatibility removal is explicit rather than mixed into
  early migrations. Full-car simulation and unsupported physical behavior remain non-goals.
- **Verification:** Checked phase dependencies, ownership rules, compatibility handoffs, public
  contract direction and completion criteria against the approved architecture and existing ADRs.
  No application tests were required for documentation-only work.
- **Browser/soak/physical checks:** Not applicable; no executable behavior changed.
- **Documentation:** All files in this directory are new specification documents.
- **Dependencies/migrations:** None. Future phases propose Socket.IO dependencies and may change
  public contracts, but this specification applies neither.
- **Compatibility/removal:** The documents permit temporary existing HTTP/raw-WebSocket behavior;
  Phase 8 owns its final removal after Phase 5 moves the frontend.
- **Remaining:** Implement Phases 1-8 in order and record actual results here.
- **Next handoff:** Start with Phase 1. Inspect current code and tests rather than treating proposed
  file names as current truth, and preserve the deny-by-default live output boundary.
