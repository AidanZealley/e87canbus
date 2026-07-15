# Phase 3: Runtime and service reduction

## Goal

Shorten the path through the controller owner without weakening ordering, bounds, failure handling
or deterministic shutdown. Collapse handoff objects and wrappers that exist only because the prior
roadmap was implemented incrementally.

Minimum production reduction: **300 lines**.

## Preconditions

- Phases 1-2 are `Verified`.
- Owner-loop ordering, overflow, command result, fatal failure and shutdown tests pass at the base.
- The Phase 1 ledger identifies exact runtime/service candidates rather than a general rewrite.

## Reduction priorities

Inspect:

- `ControllerService`, `RuntimeExecution`, adapter protocols and service snapshots.
- Live and simulated runtime adapters that translate between equivalent result shapes.
- Service-owned versus adapter-owned projection state.
- External health refresh paths and result revision remapping.
- Queue work wrappers, lifecycle flags and duplicated terminal/readiness state.
- Factories or injection seams used only to construct private test shapes.

Seek opportunities to:

- Return one result shape from live and simulated runtimes where their semantics are truly shared.
- Remove fields that are recomputed immediately or copied only for another wrapper.
- Inline one-caller forwarding methods that enforce no policy.
- Keep one source for lifecycle, boot identity, current revision and readiness.
- Separate pure projection from mutation without creating an extra “manager” layer.
- Replace test-only production factories with test fixtures where no runtime variability exists.

## Non-negotiable invariants

- One bounded queue and one mutation thread/owner remain.
- Inputs retain ingress timestamps and ordered processing.
- Overflow remains fail-safe and cannot become unbounded backpressure.
- Semantic commands receive the exact matched service revision.
- Fatal/invalid work cannot return accepted success.
- Startup/shutdown effects and adapter close order remain deterministic.
- Live and simulated modes use the same owner contract without constructing two active runtimes.

## Anti-patterns

- Replacing explicit state with several callbacks that distribute ownership.
- Merging the service and runtime into a large class solely to delete interfaces.
- Removing locks/events because tests happen to be single-threaded.
- Making the API await the controller thread without a finite timeout.
- Retaining old protocol methods as aliases after call sites move.

## Verification

Run focused owner/runtime/live/simulation/command/lifecycle suites, then:

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh
git diff --check
```

Run repeated startup/shutdown and concurrent command/reset regressions. Frontend checks are required
only if a public result or generated contract changes, which should be exceptional in this phase.

## Completion criteria

- At least 300 net production lines are removed.
- The common ingress/command path crosses fewer result/projection wrappers or adapter handoffs.
- Exactly one owner, queue, lifecycle state and current service projection remain.
- Concurrency, overflow, fatal result and shutdown behavior retain focused regression coverage.
- No compatibility methods, test-only production facades or parallel result shapes remain after
  their consumers move.
- The change is understandable as a smaller owner path, not a monolithic rewrite.

