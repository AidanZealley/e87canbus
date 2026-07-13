# Phase 6 — Simulator and API Cutover

## Goal

Run simulation commands, periodic timers, state commits, trace events, and WebSocket publication
through one ordered simulation owner. Remove direct API calls into application/runtime mutation and
make concurrent REST/WebSocket behavior deterministic.

## Simulation engine

Retain the important current behavior:

- browser button actions instruct `SimulatedNeoTrellisNode` to send real CAN frames;
- the bounded quiescence loop processes reactive device cascades;
- the same router, transition function, effect executor, and TX policy are used as live;
- the injected clock timestamps both trace entries and kernel inputs; and
- external simulated devices are not constrained by the coordinator TX policy.

Introduce a single `SimulationEngine` owner with serialized commands:

- `PressButton(index)`
- `ReleaseButton(index)`
- `StepButton(index)`
- `RunControlTimer(now)`
- `ResetSimulation`

These are simulation-composition commands, not application domain events. Press/release/step act on
the simulated device and then run buses to quiescence. Timer commands dispatch the kernel timer input
and then run effects/buses to quiescence. Reset builds a new session and startup commit.

## API ownership

- The FastAPI lifespan creates one command queue and one owner task for the `SimulationEngine`.
- REST handlers submit a command and await its result; they do not lock or call the controller
  directly.
- The periodic task submits `RunControlTimer` to the same queue.
- Reset uses the same command queue, so it cannot interleave with a press or timer.
- The owner publishes all commit and trace events in operation order. Do not launch concurrent
  broadcasts for separate operations.
- One broken WebSocket remains isolated and is logged before removal.

## Revisioned snapshots and trace sessions

- Add `revision` to application snapshots and snapshot events.
- Add a monotonically increasing simulation `session_id` or epoch that changes on reset.
- Frame identity is `(session_id, sequence)`, not `sequence` alone, because trace sequence restarts on
  reset.
- Full snapshots are still sent on initial GET/WebSocket connect/reset. Slim command and timer
  snapshots still omit trace.
- A timer publishes a snapshot only when that timer's commit changes the public application
  projection. Compare before/after the timer operation; do not compare against a stale task-local
  baseline.
- Frontend reducers ignore snapshots older than their current revision within the same session and
  keep frame rows ordered by sequence while deduplicating.

## Backpressure

Bound the simulation command queue. An overloaded browser/API receives a clear 503 response; it does
not create unbounded pending operations. This limit is separate from the CAN ingress capacity.

## Tests

- A command followed by an unchanged timer produces one snapshot publication, not the current
  redundant second snapshot.
- Concurrent press/release requests are committed and published in one deterministic order.
- Reset cannot interleave with another operation and starts a new trace session.
- Out-of-order or duplicated frontend snapshots/frames do not regress state or duplicate rows.
- A disconnected WebSocket cannot affect healthy clients and is removed/logged.
- Reactive device cascades and the 32-pass livelock cap remain covered.
- Browser commands still cannot inject `DomainEvent` or `ApplicationState` directly.
- Command-queue overflow returns 503 and leaves the engine responsive.

## Acceptance criteria

- API code contains no direct application mutation and no call to a special `tick()` entry point.
- One task owns the simulation engine.
- State publications are revisioned and ordered; trace events are session-aware.
- The redundant post-command tick broadcast is eliminated.
- Live and simulated CAN inputs use the same kernel dispatch path.
- Backend and frontend checks pass.

