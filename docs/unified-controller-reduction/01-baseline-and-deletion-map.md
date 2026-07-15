# Phase 1: Baseline and deletion map

## Goal

Establish a reproducible current-tree baseline and approve specific deletion hypotheses before any
production refactor. Map the shortest honest version of each common flow, then identify wrappers,
representations and diagnostics that do not protect observable behavior.

This phase changes no production code. It must not invent abstractions in anticipation of later
deletion.

## Inputs to inspect

Read completely:

- `coordinator/src/e87canbus/service.py`, `runtime.py`, `composition.py` and `live.py`.
- `coordinator/src/e87canbus/api/models/live.py`, `api/internal/live.py`, API lifecycle and routes.
- `coordinator/src/e87canbus/simulation/runtime.py` and selected device adapters.
- `frontend/src/live/`, `frontend/src/api/` and the live-data provider.
- `docs/reliability.md`, deployment files, ADRs 0001-0008 and the newest unified-controller log
  entries.
- Tests covering the owner loop, publication, reconnect, health, composition and frontend transport.

## Reproducible volume baseline

Record the phase-base commit and counts for:

- Backend production: tracked `*.py` under `coordinator/src/e87canbus`.
- Frontend production: tracked source under `frontend/src`, excluding `*.test.*`.
- Backend and frontend tests.
- Generated contracts and firmware output separately.
- Documentation and deployment separately.

Use physical line counts and `git diff --numstat` consistently. Store the exact command in the log
so later phases can reproduce it. Do not mix generated-schema lines into production reduction.

At minimum report:

```text
area                 files   physical lines
backend production
frontend production
tests
generated contracts
documentation
deployment/scripts
```

## Cognitive baseline

Map these flows by listing the production files, transformations and named handoff values crossed:

1. SocketCAN frame to controller commit/effect.
2. Semantic HTTP command to authoritative Socket.IO update.
3. Simulation action to virtual CAN, controller effect and UI convergence.
4. Controller commit to one browser topic update.
5. New/reconnected browser to synchronized Zustand state.
6. Settings/profile mutation to SQLite, exact cache replacement and other-client invalidation.
7. Startup, readiness, fatal failure and shutdown.

For each flow, record:

- Owner and mutation boundary.
- Files crossed on the normal path.
- Values that merely rewrap another value.
- Independently maintained representations of the same fact.
- Queues, locks and retained stores involved.
- Tests that prove externally visible behavior.

## Candidate deletion ledger

Classify candidates rather than immediately deleting them:

| Classification | Meaning |
|---|---|
| Delete | No consumer or behavior; remove completely |
| Collapse | Two layers/values express one responsibility |
| Inline | One-caller wrapper adds no policy or boundary |
| Retain | Protects a bound, safety rule, framework boundary or useful operator decision |
| Decision required | Deletion changes a public contract or accepted safety behavior |

Prioritize inspection of:

- Repeated service/runtime result and projection wrappers.
- Boundary models that copy an already-typed immutable projection field by field.
- Health/diagnostic values with no operator decision, failure policy or UI consumer.
- Publisher state duplicated between the publisher and service snapshot.
- Configuration values that have one fixed supported value.
- Composition selections or factories used only by tests.
- One-caller internal functions and pass-through API helpers.
- Frontend aliases/types that duplicate the generated live contract.
- Tests that freeze deleted private shapes instead of observable behavior.

Do not presume these are all removable. The ledger must identify consumers and the protected
behavior before assigning a deletion classification.

## Target calibration

Confirm or revise the roadmap's 1,000-line overall production target. Revision requires:

- Concrete candidate-level estimates, not intuition.
- Identification of the protected behavior that prevents each rejected deletion.
- Review approval recorded in the log.

Keep per-phase targets net-negative. Do not allocate test or generated-file deletion toward the
production target.

## Verification

No code suite is required if production files are untouched. Run:

```text
git status --short
git diff --check
```

Cross-check the flow maps against current tests and use dead-symbol/import searches to validate
consumer claims.

## Completion criteria

- Current volume counts are reproducible from the logged base commit and command.
- All seven common flows have an owner/file/handoff map.
- Every proposed deletion names the behavior and tests that must remain.
- Every retained complex mechanism names the bound, safety rule or consumer that justifies it.
- The overall and per-phase budgets are approved without counting tests/docs/generated churn.
- No production code or public contract changed.

