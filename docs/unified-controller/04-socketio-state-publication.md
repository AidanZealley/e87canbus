# Phase 4: Socket.IO live-state publication

## Goal

Add one bounded Socket.IO live-state publisher behind the unified controller service. Publish fixed,
versioned topic projections with complete reconnect synchronization and latest-state backpressure.
Retain the legacy frontend transport temporarily until Phase 5 consumes the new contract.

This phase does not move frontend ownership, send business commands over Socket.IO or persist live
event history.

## Preconditions

- Phases 1-3 are `Verified`.
- Commit changed-topic semantics and HTTP resource-change models are stable.
- Existing WebSocket connection, trace and invalidation tests are understood.

## Dependencies and ASGI composition

- Add `python-socketio` to the coordinator runtime dependencies.
- Mount one `socketio.AsyncServer`/ASGI application with the existing FastAPI app.
- Use one namespace. Do not introduce one namespace per topic.
- Preserve same-origin production operation and the exact development CORS policy.

Socket.IO session objects remain transport concerns and never enter the controller core.

## Event contract

Define fixed server events:

```text
controller.snapshot
vehicle.state
engine.state
steering.state
buttons.state
devices.state
controller.health
resources.changed
trace.batch
```

Each state event contains the Phase 1 envelope and one complete topic projection. Do not use JSON
Patch or arbitrary topic strings.

`controller.snapshot` contains all live projections and their current revisions. It is sent:

- On initial connection.
- On every reconnect not explicitly proven recovered.
- When the client reports an incompatible/missing local boot identity and requests resync.

The client must be able to discard its entire prior live store and recover from this message alone.

## Commit publication bridge

The controller owner must never wait on network clients. Build one bounded bridge from committed
state to the ASGI publisher:

- Immediate topics retain only their latest unsent projection if the bridge is busy.
- Vehicle/engine telemetry is coalesced to an initial target of 20-30 publications per second.
- Health, steering mode and button state publish promptly when changed.
- Identical projections do not publish merely because a control timer advanced.
- A newer revision replaces an older pending revision for the same topic.
- Publication failure updates transport diagnostics but cannot block CAN processing or effect
  execution.

The exact mechanism may be a thread-safe latest-topic map plus one async wakeup. Do not create an
unbounded queue of every commit.

## Trace delivery

Trace is diagnostic and isolated from normal state:

- Backend trace storage is a fixed-size ring buffer.
- Trace batches have bounded row count and publish at a bounded cadence.
- A socket joins trace delivery only through an explicit subscription transport event.
- Unsubscribe/disconnect removes membership and references.
- A slow trace client drops older diagnostic data; it never affects controller health.
- The default connection receives no continuous raw CAN trace.

Socket client events for trace subscribe/unsubscribe are transport controls, not business commands.

## Delivery and reconnection semantics

- Treat Socket.IO delivery as ordered but not durable.
- Do not persist/replay missed telemetry.
- A full snapshot is the authoritative recovery path.
- `boot_id` change causes complete client reset.
- Topic revisions reject older or duplicate messages.
- Resource-change events may be missed; reconnect causes the frontend to invalidate/refetch its
  small durable-resource set once.
- Business commands remain HTTP so an acknowledgement has an ordinary request lifecycle.

Do not depend on connection-state recovery being successful. It may be used as an optimization only
if the Python/JavaScript versions prove compatible and full resynchronization still works.

## Contract generation

Use backend Pydantic models as the source for payload schemas. Add the smallest repeatable generation
or check needed to keep TypeScript event types aligned. Generated files:

- Are never hand-edited.
- Have a check mode used in CI/repository verification.
- Do not duplicate domain behavior or CAN protocol constants.

If existing project tooling makes generated socket types disproportionately complex, use one
explicit TypeScript event map plus contract fixtures/tests and record the tradeoff. Do not introduce
a separate schema platform.

## Legacy compatibility

Keep the current raw WebSocket endpoint only while the current frontend depends on it:

- It must consume the same controller snapshots/commits, not another publisher state.
- New features target Socket.IO only.
- Its queues and trace delivery remain bounded.
- Phase 5 moves the frontend; Phase 8 removes the endpoint and adapter.

## Tests

- Initial connection receives one complete snapshot with boot ID and topic revisions.
- Reconnect/new boot produces a complete replacement snapshot.
- Older and duplicate revision fixtures are identifiable by the client contract.
- One commit publishes only changed topic projections.
- Telemetry is bounded/coalesced under a high-rate synthetic input burst.
- Slow/stalled sockets do not grow memory or delay controller inputs/effects.
- Trace is absent by default, bounded when subscribed and stops on unsubscribe/disconnect.
- Resource-change payloads carry exact resource identity/revision.
- Multiple clients receive consistent current state without shared mutable session data.
- Startup/shutdown/repeated test app construction leaves no socket publisher tasks.
- Legacy endpoint remains compatible through the same state source.

## Verification evidence

In addition to automated checks, run a bounded publication exercise that records:

- Input event rate.
- Published event rate by topic.
- Maximum pending topic count.
- Trace ring length and batch size.
- Controller queue latency/fault state.

No physical CAN or browser visual evidence is required in this phase.

## Completion criteria

- FastAPI and Socket.IO run in one ASGI composition.
- One fixed, versioned live event map covers current frontend state.
- Every connection can recover from a complete snapshot without replay.
- Controller publication cannot wait on a socket or grow an event backlog.
- Telemetry and trace rates/storage are bounded and demonstrated in tests.
- Business commands remain HTTP-only.
- Legacy WebSocket compatibility has one source and explicit Phase 8 removal ownership.
- Relevant dependency, contract-generation and repository checks pass.
