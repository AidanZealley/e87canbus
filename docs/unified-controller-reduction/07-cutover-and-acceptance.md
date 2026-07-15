# Phase 7: Integrated cutover and acceptance

## Goal

Finish the deletion pass, prove that the smaller architecture and test suite retain verified system
behavior, and reconcile measured results against the approved cognitive and production-volume
targets.

This phase is not a place to add compensating abstractions because earlier deletions were incomplete.

## Preconditions

- Phases 1-6 are at least `Implemented` with no unresolved ownership, safety, reconnect, bounded-
  resource or test-coverage blocker.
- Every temporary helper introduced during reduction has an explicit deletion check.
- The implementation log contains consistent phase-base and final production/test accounting.

## Final dead-code and facade sweep

Search production, tests and active docs for:

- Removed type, wrapper, result, projection and configuration names.
- One-caller forwarding functions and import aliases left by moved call sites.
- Duplicate public payload definitions or live-state serializers.
- Test factories that are still exposed from production code.
- HTTP reads overlapping Socket.IO live authority.
- Multiple controller, publisher, transport or trace owners.
- Compatibility routes, response snapshots and SPA fallbacks masking retired server paths.
- Diagnostic fields with no consumer or decision recorded in the Phase 1 ledger.
- Tests and fixtures that refer only to retired implementations or impossible internal states.

Delete proven remnants. Do not retain facades “for safety”; safety must be expressed by the surviving
owner and behavior-level tests.

## Accounting acceptance

From the Phase 1 base, report added/deleted/net lines for backend production, frontend production,
tests, generated contracts, documentation and deployment separately. Also report before/after:

- Production and test file/line counts.
- Test cases and suite runtime.
- Named owner/manager/service/result/projection/model concepts removed and added.
- Flow hops for all seven Phase 1 maps.
- Independently maintained contract copies.
- Runtime queues, retained stores and lifecycle owners.

Acceptance requires at least 1,000 net production lines removed unless an earlier reviewed decision
changed the target. Test/doc/generated deletion is never credited to that target. The final test
suite must also be net-negative and satisfy the Phase 6 value rubric.

## Architecture acceptance

Prove:

- One ordered controller owner handles inputs, timers, commands, faults and shutdown.
- Live and simulated compositions do not construct parallel state owners.
- HTTP commands/resources and Socket.IO live state remain non-overlapping.
- One frontend socket owner feeds current Zustand state; Query owns durable resources.
- Every queue/ring/store remains finite and has one owner.
- Default live operation remains listen-only.
- The final code has fewer handoff representations and no replacement generic framework.

## Integrated behavior

Run the completed unified-controller scenarios for emulated device convergence, idempotent commands,
vehicle staleness/reset, durable conflicts/invalidation, reconnect/restart reconciliation and inbox/
output/persistence/slow-client failures.

## Browser and retention acceptance

Use isolated development and production services. Repeat the route/theme/800x480 matrix, forced
restart and sustained traffic used by the completed roadmap. Record comparable socket/listener/
store/DOM/heap/backend/inbox/publisher measures. The former development crash must not reproduce;
do not lower counts by disabling supported instrumentation or features.

## Repository verification

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

Run firmware checks when touched and record optional physical checks as unavailable rather than
substituting simulation claims.

## Completion criteria

- The approved net production reduction target is met with honest accounting.
- Every common flow crosses fewer concepts or files without obscuring its owner.
- The test suite is smaller, value-classified and free of implementation archaeology.
- No compatibility facade, parallel payload, dead configuration or test-only production seam
  remains.
- All automated, browser, reconnect, overload and retention acceptance passes.
- Default-deny physical output and all evidence gates remain intact.
- Active documentation describes the smaller actual system.
- The final report lists what remains complex and why rather than claiming minimality without
  evidence.
