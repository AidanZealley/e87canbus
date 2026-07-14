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
| 1 — Profile domain model | Verified | 2026-07-14 | Version-1 integer curve contract implemented |
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

### 2026-07-14 — Phase 1: profile domain model verified

- **Status:** Verified
- **Scope:** Implemented the versioned immutable curve definition, stored-profile metadata value,
  validation, canonical serialization, fingerprinting, built-in definition and calculation
  projection required by Phase 1.
- **Changed:** Added the fixed eight-point integer-unit domain contract and sole built-in definition
  in `coordinator/src/e87canbus/features/steering.py`. `SteeringConfig` now derives its transitional
  float curve from that definition, with no runtime activation or ownership change. Added focused
  domain tests and updated existing application/simulation expectations for the documented
  half-per-mille quantization tolerance.
- **Decisions:** Profile names are trimmed, non-empty and limited to 100 characters. Profile IDs
  use canonical lowercase hyphenated UUID text. Timestamps use UTC ISO 8601 with six fractional
  digits and `Z`. Definition canonical bytes are compact key-sorted UTF-8 JSON; the fingerprint is
  its lowercase SHA-256 digest. These choices make persisted values deterministic without adding
  persistence or API types.
- **Verification:** `uv run pytest -q` (249 passed); `uv run ruff check .`; `uv run mypy
  coordinator/src/e87canbus`; `uv run python scripts/generate_custom_protocol.py --check`; and
  `git diff --check` all passed. The existing FastAPI test dependency emitted one upstream
  Starlette `httpx` deprecation warning.
- **Documentation:** Documented authoritative units, validation ownership, schema/interpolation
  support, canonical bytes, fingerprint scope and timestamp format in `coordinator/README.md`.
- **Dependencies/migrations:** None. The existing runtime float field remains as a projection for
  compatibility and is scheduled for removal in Phase 3.
- **Remaining:** None for Phase 1. Persistence, runtime activation, API, editor and smooth
  interpolation remain in later phases.
- **Next handoff:** Phase 2 can persist the domain values directly. It must preserve the exact
  integer fields, UUID/name constraints, canonical timestamps and optimistic revision contract;
  it must not fingerprint stored metadata.

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
