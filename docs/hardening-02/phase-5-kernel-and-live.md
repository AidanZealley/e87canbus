# Phase 5 — Single-Owner Kernel and Live Cutover

## Goal

Make startup, received frames, timers, adapter faults, and shutdown inputs to one state-owning
kernel. The live runner becomes composition and waiting code only.

## Kernel contract

Evolve `CoordinatorRuntime` into a `CoordinatorKernel` with one public input method. Use a closed
runtime-input union such as:

- `KernelStarted(now)`
- `ReceivedCanFrame(network, frame, received_at)` from phase 2
- `ControlTimerElapsed(now)`
- `CanReaderFailed(network, failed_at, message)`
- `EffectExecutionFailed(network, failed_at, message)`
- `ShutdownRequested(now)`

`CoordinatorKernel.dispatch(input) -> Commit | None` is the only state-changing entry point.
Delete `start()`, `process_frame()`, `tick()`, and `drain_pending()` compatibility entry points before
the phase completes; simulator cutover work may be developed on the same branch, but phase 5 is not
complete until phase 6 callers have a temporary adapter that does not mutate state outside
`dispatch`.

## Commit value

```python
@dataclass(frozen=True)
class Commit:
    revision: int
    snapshot: ApplicationSnapshot
    effects: tuple[ApplicationEffect, ...]
    state_changed: bool
```

- Revision starts at one for the startup commit and increases for every accepted domain transition,
  including a transition with effects but an unchanged externally visible snapshot.
- Unknown CAN traffic updates runtime/network health if desired but need not create an application
  commit.
- The kernel owns current state and the next revision. No outer component can assign either.
- Publication callbacks receive `Commit` after state commit. They cannot mutate the kernel.

## Live loop

- Reader threads continue to do only receive, timestamp, and bounded enqueue.
- The main thread is the only caller of `kernel.dispatch` and the effect executor.
- Periodic scheduling enqueues or directly dispatches `ControlTimerElapsed` in sequence with inbox
  processing; use the existing drift-resistant deadline accumulator and missed-tick resynchronizing
  rule.
- A reader reports normalized repeated failures as `CanReaderFailed` and exits. The main loop must
  not continue indefinitely with a dead network thread.
- Effect failures are converted into a later kernel fault input rather than recursively dispatching
  during effect execution.
- Shutdown is explicit, idempotent, and followed by bounded reader joins and adapter cleanup.
- Return a non-zero exit code for overflow or fatal reader/effect failure.

## Runtime health

Define a small explicit runtime-health value rather than leaving `CanHealth` as unread mutable data.
At minimum it records last observation time and current fault/overflow status per network. It is
available in a diagnostic snapshot without becoming application decision state.

Do not broadcast continuously changing "age" values. Publish timestamps and status transitions;
consumers can derive age from their own current time.

## Tests

- A mixed sequence of startup, frames, and timers produces deterministic revisions and effects.
- Observation timestamps survive queue delay unchanged.
- No two threads call `dispatch` concurrently in the live composition.
- A reader fault becomes a kernel input and causes clean non-zero shutdown.
- An effect failure is reported on the next loop turn and cannot recursively re-enter the kernel.
- Tick resynchronization still produces one tick after a large clock jump, not a catch-up burst.
- Sustained unknown traffic cannot prevent timer dispatch indefinitely.
- Reader and main-loop threads stop within bounded test time.

## Out of scope

- Browser API publication; phase 6 consumes commits.
- Steering actuator behavior.
- Persistence or replay of commits.

## Acceptance criteria

- The kernel is the only owner of application state and revision.
- Application/runtime modules contain no threading or queue primitives.
- The live runner has one state-consuming thread and bounded ingress.
- `start`, `process_frame`, and `tick` are not public mutation paths.
- A dead reader cannot fail silently while the coordinator reports normal operation.
- All checks pass.

