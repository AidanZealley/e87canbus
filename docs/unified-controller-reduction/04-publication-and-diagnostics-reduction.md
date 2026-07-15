# Phase 4: Publication and diagnostics reduction

## Goal

Reduce the bounded Socket.IO publisher and health/diagnostic machinery to the smallest set that
prevents the observed failure modes and supports real operator decisions.

Minimum production reduction: **300 lines**.

The former browser crash, stalled-client isolation and reconnect correctness are protected outcomes.
This phase may remove counters or layers, but not the bounds that enforce those outcomes.

## Preconditions

- Phases 1-3 are `Verified`.
- Phase 1 maps every publisher queue/store and every health field to consumers and decisions.
- Existing browser/soak measurements provide a comparison baseline.

## Publication simplification

Inspect:

- Pending-topic coalescing and timer scheduling.
- Trace ring and subscription ownership.
- Per-client Engine.IO queue saturation handling.
- Publisher-to-service health feedback and recursion avoidance.
- Snapshot and topic envelope construction.
- Counters retained in both publisher internals and service projections.

Preserve at minimum:

- One complete snapshot on connect/resync.
- Latest-value coalescing for high-rate telemetry.
- Finite per-client outbound capacity and slow-peer disconnection.
- Opt-in bounded trace with reset/session identity.
- Controller-owner independence from socket send latency.
- One socket/listener set across frontend remounts and navigation.

Prefer one event-loop scheduling mechanism and one source for each queue/subscriber count. Remove
custom machinery when Socket.IO/Engine.IO already supplies the exact bounded behavior, but verify
the installed version rather than assuming framework internals.

## Diagnostic simplification

Retain a diagnostic only when it answers at least one of:

- Is the process/controller ready?
- Did an input/effect/persistence/publisher failure occur?
- Is a bounded queue/ring saturated or approaching its configured policy?
- Which configured capability/network is unavailable?
- Did a slow client get isolated?

Candidates without an operator, UI, test acceptance or failure-policy consumer should be removed or
kept internal rather than projected through every layer. Prefer a small current status plus a few
monotonic counters to replicated diagnostic trees.

Do not remove `live`/`ready`, fatal fault truth, queue capacity/overflow truth or evidence required
to distinguish controller failure from browser disconnection.

## Browser and soak verification

Run isolated development and production builds. Include:

- Initial synchronization and forced backend restart.
- A stalled or saturated client alongside a healthy client.
- Expected and elevated telemetry/command traffic.
- Trace subscribe/unsubscribe cycles.
- Same-document route cycles after lazy loading.

Record sockets, listeners, documents, DOM nodes, trace size, heap after GC, backend RSS, inbox depth/
latency and the smaller final diagnostic shape. Counts must plateau after warm-up and the connection
badge must return from `Reconnecting` to `Connected`.

## Verification

Run focused publication/health/reliability tests plus all backend/frontend/static/generated checks
listed in Phase 2. Run `git diff --check` and dead-field searches.

## Completion criteria

- At least 300 net production lines are removed.
- Bounded publication uses fewer scheduling/state/feedback concepts.
- Every remaining public diagnostic field has a named consumer or operator decision.
- Stalled clients remain isolated and no controller path awaits socket delivery.
- Reconnect, boot reset, trace ownership and the original crash regression pass in development and
  production.
- No diagnostic complexity is merely moved into the frontend or logs.

