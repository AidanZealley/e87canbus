# Phase 2 — Timestamped, Bounded Ingress

## Goal

Capture observation time when live frames enter the process and prevent overload from becoming an
unbounded queue of increasingly stale traffic.

## Problem being fixed

The current reader threads enqueue `RoutedCanFrame`, and `CoordinatorRuntime.process_frame()` reads
the clock only when the main thread eventually dequeues it. Under backlog, an old speed frame can
therefore appear fresh. The queue is unbounded, so the duration of this false-fresh window has no
architectural limit.

## Design

### Runtime input envelope

Add a frozen transport-neutral input type next to the runtime boundary:

```python
@dataclass(frozen=True)
class ReceivedCanFrame:
    network: CanNetwork
    frame: CanFrame
    received_at: float
```

- `read_frames_into_queue` gains an injected monotonic clock and constructs this type immediately
  after `bus.receive()` returns.
- The runtime records CAN health and passes event time to the application from `received_at`; it
  does not read the clock while processing a received frame.
- The simulator constructs the same input immediately when draining an in-memory endpoint, using
  its injected clock. A fake clock must remain deterministic.
- `RoutedCanFrame` may remain a wire-routing value inside the protocol router during this phase, but
  it is no longer the live queue item. Delete any compatibility overload that accepts a bare routed
  frame before completing the phase.

### Bounded live inbox

- Add `runtime_inbox_capacity` to configuration with a conservative explicit default.
- The live composition creates `queue.Queue[ReceivedCanFrame]` with that maximum size.
- Reader threads use non-blocking insertion. They must never block a CAN receive thread behind a
  slow consumer.
- On `queue.Full`, atomically latch an overflow condition, log it once per incident, set the live
  stop event, and make `run_live` return non-zero after cleanup. With no actuator currently present,
  terminating is safer than continuing with unknowable latency.
- Keep the overflow latch and threading primitives in `live.py`; do not put locks or events in the
  runtime or application.
- Phase 8 replaces termination-only behavior with an explicit actuator failsafe before shutdown.

### Queue latency observability

At dequeue, calculate `processing_started_at - received_at` for logging/metrics only. Add a warning
threshold in config. Do not use this processing delay to rewrite observation time.

## Tests

- A fake-clock reader stamps a frame at receive time; advancing the clock before processing does not
  change CAN health or speed observation time.
- An old queued speed event cannot refresh validity based on dequeue time.
- Queue capacity is applied by `run_live` composition.
- Overflow stops the live loop, logs one clear error naming the network, cleans up buses/readers, and
  returns non-zero.
- No tests use real sleeps to establish timestamp or overflow behavior.
- Simulator trace and runtime observation use the same fake clock.

## Out of scope

- Coalescing raw CAN frames. Replacement semantics are not known until a verified decoder says a
  message represents replaceable state.
- Priority queues. Edge-triggered input must not be silently reordered.
- Application state redesign; phase 3 consumes the timestamped event shape.

## Acceptance criteria

- No safety freshness decision uses the clock value at queue-dequeue time.
- The live inbox has a finite configured maximum.
- Queue overflow is visible and terminates the current no-actuator runner cleanly.
- `RoutedCanFrame` is not used as a live queue item.
- All checks pass.

