# Phase 6: Test-suite reduction

## Goal

Reduce the time and cognitive effort required to understand and maintain the test suite. Preserve
tests that protect supported behavior, safety, concurrency, bounds and real regressions; remove
tests whose only value was scaffolding a transitional implementation or proving that deleted code
still has not returned.

This phase must be net-negative in test code. It does not contribute to the 1,000-line production
target and must not weaken production behavior to make tests easier.

## Preconditions

- Phases 1-5 are `Verified` or at least `Implemented` with stable surviving boundaries.
- Production deletion has finished far enough that private structures are not still moving.
- Phase 1 recorded test count, line count and runtime by backend/frontend suite.

## Test value rubric

Every retained test should provide at least one clear value:

| Value | Examples |
|---|---|
| Public contract | Supported HTTP/Socket.IO shapes, errors and durable-resource behavior |
| Safety invariant | Default-deny output, capability validation, fail-safe shutdown |
| Concurrency/bound | Ordering, overflow, stalled peer, lifecycle cleanup, listener ownership |
| Real regression | A bug observed in use, such as stuck reconnecting or retained-state growth |
| Domain example | Non-obvious curve, protocol, freshness or device behavior |
| Integration confidence | One end-to-end test replacing many mocked layer tests |

Tests with none of these values are deletion candidates.

## Presumptive deletion candidates

- Assertions that a private dataclass has or lacks a field after its consumers are gone.
- Tests that import a deleted module name only to prove architecture searches no longer find it.
- Repeated 404 tests for retired routes when absence is not a current security/ownership boundary.
- Tests that construct states impossible through typed public composition merely to exercise a
  defensive branch with no credible caller.
- Mock-heavy tests that only verify one private method called another private method.
- Exact private counter/revision/order assertions with no public, safety or concurrency meaning.
- One test per wrapper layer when one surviving boundary test proves the behavior.
- Snapshot-style assertions duplicating more focused contract tests.
- Parametrized cases that execute the same branch and add no boundary example.
- Historical compatibility tests, import aliases and fixture shapes from removed implementations.
- Tests for test-only production factories or accessors; remove the production seam as well.

A retired-route 404 may remain when the SPA could otherwise mask the route, when exposure would
restore an overlapping authority, or when production trust boundaries depend on absence. Record
that reason explicitly rather than retaining every negative route test automatically.

## Tests to retain carefully

- Single-owner order, queue overflow and fatal-result truth.
- Default-deny physical output and invalid capability composition.
- Generated CAN codec vectors and simulation-to-production path parity.
- HTTP command/resource and Socket.IO public contracts.
- Reconnect snapshot, `boot_id` reset and stuck-reconnecting regression.
- Slow-client isolation, bounded trace/store/listener behavior and soak acceptance.
- SQLite revision conflicts and committed-winner preservation.
- Startup/shutdown resource cleanup and readiness transitions.
- 800x480 route behavior and meaningful accessibility/status behavior.

These may still be consolidated. “Retain” means retain coverage at the most useful boundary, not
retain every existing test function.

## Consolidation method

For each cluster:

1. Name the supported behavior.
2. Identify the highest boundary that proves it with useful failure output.
3. Keep focused lower-level cases only for genuinely distinct algorithms, concurrency or failure
   injection that the boundary test cannot diagnose.
4. Delete superseded tests and their obsolete fixtures/helpers together.
5. Run mutation-by-inspection: state the production defect each retained test would catch. If no
   plausible defect can be named, reconsider the test.

Do not replace meaningful unit tests with a single enormous end-to-end test. The goal is a smaller,
intentional pyramid, not fewer assertions at any cost.

## Accounting

Report before/after by suite:

```text
suite                  files   test cases   physical lines   runtime
backend
frontend unit
frontend component
browser/integration
firmware
```

Also report fixtures/helpers removed, tests consolidated, and negative regressions retained with
their current contract justification. Coverage percentage may be reported as a warning signal but
is not an acceptance target.

## Verification

Run the complete surviving suite and all static/generated/build checks:

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_live_contract.py --check
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh

pnpm test
pnpm lint
pnpm typecheck
pnpm build

git diff --check
```

Run the browser regressions for any frontend tests removed. Run firmware checks if firmware tests or
fixtures change.

## Completion criteria

- Test files, lines and cases are net-negative with honest before/after accounting.
- Every retained test cluster maps to the value rubric.
- Redundant private-layer, impossible-state and implementation-archaeology tests are removed.
- Negative route/import regressions remain only when absence is a current contract and the reason is
  recorded.
- Obsolete fixtures, mocks, helper types and test-only production seams are removed with their tests.
- Complete backend/frontend/static/generated/build checks pass.
- No meaningful safety, concurrency, public-contract or observed-bug regression loses coverage.

