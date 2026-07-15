# Unified controller reduction implementation log

This is the durable handoff for the deletion-led simplification pass. It records measured reduction,
behavior preserved and any target that could not be met safely. It must not count moved, generated
or reformatted code as simplification.

## Phase status

| Phase | Status | Last entry | Production reduction | Notes |
|---:|---|---|---:|---|
| 1 — Baseline and deletion map | Verified | 2026-07-15 | 0 | Baseline, seven flow maps and candidate ledger recorded |
| 2 — Contract/model consolidation | Verified | 2026-07-15 | 90 | Typed values cross framework boundaries directly; target variance accepted |
| 3 — Runtime/service reduction | Not started | — | — | Shorten the single-owner path |
| 4 — Publication/diagnostics reduction | Not started | — | — | Preserve bounds with fewer mechanisms |
| 5 — Composition/frontend seams | Not started | — | — | Remove construction and consumption layers |
| 6 — Test-suite reduction | Not started | — | — | Remove implementation archaeology and redundant tests |
| 7 — Cutover/acceptance | Not started | — | — | Prove overall reduction and behavior |

## Current handoff

Start Phase 3 from the controlling Phase 2 commit once recorded; its hash is pending and must not be
inferred from this uncommitted handoff. The recorded roadmap base remains
`a31d2f8016bb3d6766425ae5fb244a5058fecc63`; reproduce cumulative accounting with the commands in
`phase-1-baseline.md`. Collapse `RuntimeExecution`, `ControllerCommandResult`, the boolean-to-
`queue.Full` reader adapter and duplicate simulated/service observation projections where their
facts can stay on canonical `Commit`, service and adapter owners. Preserve the one bounded ordered
inbox, owner-thread mutation, ingress timestamps, commit-before-effect behavior, command revision
matching, production-codec simulation, fatal-result rejection and default no-TX composition. Do not
pull the Phase 4 publisher/service/public diagnostic consolidation forward. Phase 2's 90-line target
variance and direct FastAPI dataclass response boundary are accepted. No compatibility path exists
or is authorized.

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

### 2026-07-15 — Phase 2: typed boundary values replace copied representations

- **Status:** Verified
- **Scope:** Consolidated live steering types, nested Socket.IO projection adaptation and durable
  settings/profile response serialization. Protocol versioning, payload fields, command handling,
  repository ownership, publisher behavior and all runtime/safety paths were intentionally left
  unchanged.
- **Deletion hypothesis:** FastAPI already serializes the immutable domain settings/profile
  dataclasses at its real wire boundary, so three manually maintained dictionary serializers were
  redundant. Pydantic can validate matching nested dataclass fields directly without reconstructing
  telemetry, curve points, devices and steering observations field by field. The frontend live
  contract already owns the active steering shape, so the durable API module did not need a second
  structural copy.
- **Production accounting:** Phase base
  `b07ae03a38bb13308cf225ab1912cffb1d9dd82a`. Backend production: +35/-107, net -72 across five
  touched files under `coordinator/src/e87canbus/api`: `internal/settings.py` +5/-22,
  `internal/steering.py` +11/-34, `models/live.py` +6/-41, `routes/settings.py` +3/-4 and
  `routes/steering.py` +10/-6 (directory totals: internal +16/-56, models +6/-41, routes
  +13/-10). Frontend production: `frontend/src/api/steering.ts` +4/-22, net -18. Total
  production: +39/-129, net -90; 0 files added or deleted and 6 touched. Tests +0/-0;
  documentation is this log +93/-6 in `docs/unified-controller-reduction`; generated artifacts
  +0/-0; temporary compatibility +0/-0. Cumulatively from roadmap base `a31d2f8`, production is
  the same +39/-129/-90 and documentation is +488/-8 across the Phase 1 baseline and this log. The
  largest additions are typed return annotations/imports in the
  steering routes (+10 lines) and direct typed return shapes in the steering use cases (+11); they
  replace dictionary-shaped boundaries and enable the larger serializer deletion in this phase,
  not a deferred abstraction.
- **Cognitive accounting:** Operational/durable/transport owners remain unchanged. Removed named
  production concepts: `settings_to_dict`, `definition_to_dict`, `profile_to_dict` and the
  independent frontend `SteeringCurvePoint` declaration; the frontend active curve, definition and
  interpolation names remain only as aliases derived from `SteeringState`. Added concepts: 0.
  Settings/profile flows retain the same file hops but lose the domain-to-private-dictionary
  transformation. Live publication retains one Pydantic wire adapter while removing repeated nested
  telemetry, curve-point, device and actuator reconstruction inside it. Queues 0/0, schemas 0/0,
  contract copies added/removed 0/2 (manual backend response dictionaries and the independently
  maintained frontend steering structure).
- **Changed:** Settings and steering-profile use cases now return canonical immutable domain values;
  FastAPI performs the only response serialization. Matching nested domain/service values enter the
  existing Pydantic live models through `model_validate(..., from_attributes=True)`. Frontend
  steering API types derive from `SteeringState`. Explicit mappings remain where names differ or
  policy combines owners, notably public network IDs and controller health summaries.
- **Protected behavior:** Exact settings/profile JSON, strict request rejection, revision conflicts,
  persistence and resource-change events pass unchanged. Socket.IO v1 schema generation, complete
  reconnect snapshots, `boot_id`/revision/topic semantics, bounded publication and visible malformed
  boundary failure remain intact. No controller owner, queue, transport, grant or lifecycle path was
  touched.
- **Tests:** Retained all authoritative public payload/schema, settings/profile/command API, SQLite,
  live publication, reconnect, frontend live-store/transport and Query ownership tests. No test was
  removed or added: there was no serializer-private test to delete, and the existing public payload
  assertions directly prove the useful contract. Safety, bounds, real regressions and domain examples
  remain in the full suite.
- **Test accounting:** Before/after remains 32 backend files, 502 cases and 7,525 physical lines;
  24 frontend files, 88 cases and 3,508 lines. The full backend run passed in 10.28 seconds; frontend
  passed 30 Node tests in 0.26 seconds and 58 Vitest tests in 4.14 seconds. Test value and count are
  unchanged.
- **Verification:** Focused settings/profile/live-contract/live-publication run passed 45 tests.
  Full `uv run pytest -q` passed 502 tests with the existing Starlette/httpx deprecation warning;
  `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus` (61 source files),
  `uv run python scripts/generate_live_contract.py --check`,
  `uv run python scripts/generate_custom_protocol.py --check` and `git diff --check` passed.
  `pnpm test` passed 30 unit and 58 component tests; `pnpm lint`, `pnpm typecheck` and `pnpm build`
  passed with 2,968 transformed modules. Dead-symbol searches find no removed serializer or copied
  frontend active-curve declaration.
- **Browser/soak/physical checks:** Not run; wire payload assertions and frontend consumption tests
  cover this representation-only change. No physical CAN or steering behavior was changed or
  claimed.
- **Dependencies/migrations:** None. No package, lockfile, SQLite schema, live schema, custom CAN
  protocol, firmware or generated artifact changed.
- **Compatibility/removal:** None. No alias, facade, deprecated route, parallel payload or temporary
  path was introduced; therefore no consumer, removal condition or later removal phase applies.
- **Target variance:** Net production reduction is 90 rather than the nominal 200. Further deletion
  in this phase would require removing strict Pydantic request/wire validation, inlining policy-bearing
  API use cases, or pulling Phase 3 result/projection and Phase 4 diagnostic ownership work forward.
  Those moves would weaken a boundary or overlap sequential phases. The measurable contract-copy and
  transformation reduction is retained for review rather than adding speculative machinery or
  cosmetic churn.
- **Remaining:** None after controlling-agent review accepted correctness, accounting and the
  target variance.
- **Next handoff:** After review, Phase 3 can collapse `RuntimeExecution`, command result and adapter
  projection handoffs. Phase 4 remains responsible for publisher/service/public diagnostic copies;
  neither was duplicated or modified here.

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
