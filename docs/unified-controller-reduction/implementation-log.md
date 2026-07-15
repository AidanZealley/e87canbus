# Unified controller reduction implementation log

This is the durable handoff for the deletion-led simplification pass. It records measured reduction,
behavior preserved and any target that could not be met safely. It must not count moved, generated
or reformatted code as simplification.

## Phase status

| Phase | Status | Last entry | Production reduction | Notes |
|---:|---|---|---:|---|
| 1 — Baseline and deletion map | Verified | 2026-07-15 | 0 | Baseline, seven flow maps and candidate ledger recorded |
| 2 — Contract/model consolidation | Not started | — | — | Remove parallel representations and adapters |
| 3 — Runtime/service reduction | Not started | — | — | Shorten the single-owner path |
| 4 — Publication/diagnostics reduction | Not started | — | — | Preserve bounds with fewer mechanisms |
| 5 — Composition/frontend seams | Not started | — | — | Remove construction and consumption layers |
| 6 — Test-suite reduction | Not started | — | — | Remove implementation archaeology and redundant tests |
| 7 — Cutover/acceptance | Not started | — | — | Prove overall reduction and behavior |

## Current handoff

Start Phase 2 from Phase 1 commit after review. The recorded roadmap base is
`a31d2f8016bb3d6766425ae5fb244a5058fecc63`; reproduce cumulative accounting with the commands in
`phase-1-baseline.md`. Consolidate boundary contracts without weakening Pydantic validation,
Socket.IO v1, revision/conflict behavior or exact Query cache ownership. Prefer removing
field-by-field adapters and independently maintained frontend types over introducing another schema
platform. No compatibility path exists or is authorized.

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

### 2026-07-15 — Phase 1: reproducible baseline and deletion ledger

- **Status:** Verified
- **Scope:** Measured the clean current tree at
  `a31d2f8016bb3d6766425ae5fb244a5058fecc63`, mapped all seven required common flows and classified
  candidate reductions. Production code, tests, generated artifacts, deployment and public
  contracts were intentionally unchanged.
- **Deletion hypothesis:** Later phases can collapse repeated `Commit`/`RuntimeExecution`/
  `SimulationResult` handoffs, simulated/service observation snapshots, publisher/service/public
  diagnostics, field-by-field live/resource adapters, handwritten frontend contract copies and
  test-only composition/transport seams. The canonical controller/service owners, bounded queues,
  strict public validation, safety grants and reconnect semantics are retained.
- **Production accounting:** Base and after are identical: backend 61 files/8,650 physical lines;
  frontend 134/9,170. Added 0, deleted 0, net 0; no production file was added, deleted or touched.
  Largest production-code additions: none. Tests remain 56 files/11,033 lines; generated live
  contract 1/1,277; deployment/scripts 8/463; firmware source 3/150. Documentation changes only:
  `phase-1-baseline.md` +323/-0 and this log +77/-7, for `docs/unified-controller-reduction`
  +400/-7 (one added and one touched file) and a documentation after-state of 67 files/9,264
  physical lines. Generated artifacts and temporary compatibility are each 0 files/0 lines. The
  exact tracked-file count command and cumulative `git diff --numstat` method are in
  `phase-1-baseline.md`.
- **Cognitive accounting:** Before/after production is unchanged: one operational owner, one
  operational queue, six state topics, one frontend transport/store path, three publisher stores
  and one bounded Engine.IO queue per peer. Named production concepts, flow hops, queues, schemas
  and contract copies added/removed: 0/0. The approved later target is removal of 6–10 wrapper/
  projection/diagnostic/selection concepts and 1–3 rewrap hops from each touched flow without
  adding an owner, queue or schema platform.
- **Changed:** Added the factual volume/cognitive baseline, owner inventory, seven flow maps,
  consumer-backed deletion ledger, compatibility inventory, target calibration and test
  disposition. Updated this status and handoff only. No abstraction, route, event, model, queue,
  configuration value or production behavior changed.
- **Protected behavior:** Existing tests and source inspection identify the single bounded ordered
  owner, ingress timestamps, production-path simulation, default no-TX live composition, explicit
  rate-limited grants, Socket.IO/HTTP ownership split, complete reconnect snapshot, `boot_id`
  replacement, bounded publication/trace/peer retention, fatal-result rejection, exact durable
  invalidation and honest readiness/shutdown as non-negotiable.
- **Tests:** Retained suites are classified in `phase-1-baseline.md` as public behavior, safety,
  concurrency/bounds, real regressions and useful domain examples. No tests were added, changed,
  removed or consolidated. Later Phase 6 candidates are only tests tied exclusively to wrappers,
  private factories, repeated serializer layers or unreachable retired internals; safety/public
  negative guarantees remain.
- **Test accounting:** Before/after is 32 backend files, 502 collected cases and 7,525 physical
  lines; 24 frontend files, 88 cases and 3,508 physical lines. Backend collection took 0.44 s.
  Frontend verification passed 30 Node cases in 0.21 s and 58 Vitest cases in 3.66 s. No test value
  was removed.
- **Verification:** `uv run pytest --collect-only -q` collected 502 tests with the existing one
  Starlette/httpx deprecation warning. `pnpm test` passed 30 unit and 58 component tests; existing
  Node experimental-module and missing local Fig shell-hook notices were non-failing. Consumer and
  dead-path `rg` searches confirmed the named wrappers remain locally consumed and retired aliases/
  transports occur only in historical documentation or explicit public-absence tests.
  `git status --short` was empty before work; final `git diff --check` and the untracked-document
  equivalent passed, with only the two intended documentation paths present.
- **Browser/soak/physical checks:** Not run; this phase changes documentation only. The prior
  unified-controller final browser/soak evidence remains applicable. Real CAN TX and physical
  steering were not enabled and no physical behavior is claimed.
- **Dependencies/migrations:** None. No dependency, lockfile, generated schema, SQLite schema,
  protocol or firmware change.
- **Compatibility/removal:** None. Raw `/ws`, snapshot/curve-state HTTP reads, response snapshots,
  legacy owner loops and internal aliases were already removed. Current Socket.IO v1 and semantic
  HTTP contracts are current public surfaces, not compatibility paths. No consumer/removal
  condition applies.
- **Target variance:** Phase 1 correctly changes 0 production lines. Candidate-level estimates
  support retaining the 1,000-line cumulative production target: approximately 200–300 lines in
  Phase 2, 350–500 in Phase 3, 300–400 in Phase 4 and 200–300 in Phase 5. These are review budgets,
  and tests/docs/generated churn does not count.
- **Remaining:** None for Phase 1 after final diff verification.
- **Next handoff:** Phase 2 should first remove duplicated contract representations and mapping
  layers while preserving strict public schemas and exact cache/revision behavior. Expected later
  deletions are the Phase 3 runtime/service result and projection wrappers, Phase 4 diagnostic
  copies and Phase 5 test-only composition/frontend lifecycle seams.
