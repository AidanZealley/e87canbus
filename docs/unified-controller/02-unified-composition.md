# Phase 2: Unified controller and API composition

## Goal

Create one controller-service lifecycle that can run behind FastAPI with selected physical or
simulated adapters. Remove the architectural split in which the live runner owns SocketCAN while a
separate API owns `SimulationEngine`, but preserve current external behavior until later transport
phases migrate its consumers.

This phase does not add Socket.IO, redesign frontend state, enable real CAN TX or remove compatibility
endpoints still required by the current frontend.

## Preconditions

- Phase 1 contracts and regression baseline are `Verified`.
- The current live and simulation lifecycles have been traced from startup through shutdown.
- Existing CLI behavior and deployment documentation are understood.

## Controller service

Introduce one composition-owned `ControllerService` (name may vary) whose responsibilities are:

- Own the controller/kernel, selected protocol router and effect executor.
- Own one bounded runtime inbox.
- Run one dedicated owner loop for dispatch and ordered effect execution.
- Start/stop selected CAN readers and simulated device adapters.
- Accept typed operational inputs and return a future/acknowledgement to API callers.
- Expose immutable latest snapshot, diagnostics and commit notifications without permitting direct
  mutation.
- Shut down deterministically and execute the existing safe shutdown transition.

A dedicated controller-owner thread with a standard bounded queue is preferred if it keeps
SocketCAN and hardware timing isolated from the ASGI event loop. Async API handlers may await a
thread-safe future. Do not move blocking CAN receives or effect I/O onto the ASGI event loop merely
to make every component `async`.

If current evidence supports a simpler equivalent owner, document it. The invariant is one ordered
state owner, not a required concurrency primitive.

## Runtime work items

The service inbox may contain composition work in addition to closed kernel inputs, for example a
developer action directed at an emulated device. Such work must be explicitly typed and handled by
the same runtime owner. An emulator action may emit a CAN frame; it may not inject a domain event or
edit kernel state.

Keep kernel `dispatch` as the only operational-state mutation path.

## Adapter selection

Resolve adapter ownership at startup from validated configuration. Support the concepts:

```text
CAN network adapter: socketcan | virtual | disabled
custom device source: physical | emulated | observer | disabled
steering capability: simulated | physical-evidence-gated | absent
```

Configuration validation must reject:

- More than one ingress authority for the same device capability.
- A physical and emulated device both emitting the same role's input.
- A live transmitter without an explicit network TX grant.
- Simulation-only protocol decoding in a live production router.
- A physical steering adapter without its separate evidence-backed implementation/grant.

Convenient presets such as `live` and `simulated` may expand to explicit adapter selections. Avoid
scattered `if simulation` branches after composition.

## FastAPI lifecycle

`create_app` should receive or construct one controller service and repositories. Its lifespan:

1. Initializes/migrates SQLite once.
2. Loads and validates durable desired configuration.
3. Starts the controller service and selected adapters.
4. Publishes readiness only after startup commit/output synchronization.
5. Stops accepting commands during shutdown.
6. Requests safe controller shutdown.
7. Stops readers/adapters and closes repositories.

Routes obtain snapshots and submit commands through the service boundary. They never receive a
mutable `SimulationEngine` or kernel reference.

## Simulation ownership during migration

Refactor current `SimulationEngine` responsibilities deliberately:

- Kernel/controller state moves under `ControllerService` ownership.
- Virtual bus and simulated devices remain adapters/nodes.
- Simulation reset and device actions are typed runtime work submitted to the owner.
- Timer production has one owner.
- Snapshot identity comes from the controller boot/revision contract.
- Trace remains bounded and separately identified.

Temporary facades may preserve existing API test construction, but they must delegate to the same
controller service and be assigned removal in Phase 8. Do not leave two independently mutable
runtime models.

## CLI and operator behavior

Provide one canonical entry point capable of selecting composition, for example:

```text
e87canbus run --mode simulated
e87canbus run --mode live
```

Existing entry-point names may remain as thin compatibility aliases if operator scripts depend on
them. An alias must resolve configuration and invoke the same application composition; it must not
construct the retired architecture.

Live mode exposes the API even when all transmit capabilities remain absent. Development-only
simulation mutation routes are unavailable or fail explicitly outside a composition containing the
corresponding emulator.

## Tests

- App startup/shutdown starts and stops one controller service exactly once.
- Live listen-only composition opens configured readers and grants no transmitters.
- Simulated composition uses virtual networks and the same kernel/effect boundaries.
- Invalid duplicate device authority fails configuration before startup.
- API commands cannot mutate kernel state outside the service inbox.
- SocketCAN reader timestamps and bounded overflow behavior remain intact.
- Timer, reset, effect failure and fatal session behavior have one owner.
- Existing API and current frontend-facing WebSocket behavior remain compatible where retained.
- CLI compatibility aliases invoke the unified composition.
- Repeated app construction in tests does not leak threads, readers or tasks.

## Documentation

- Update coordinator operation documentation with the canonical entry point and adapter presets.
- Document development-only route availability and default listen-only live behavior.
- Mark every compatibility facade/alias and its removal owner.

## Completion criteria

- Live and simulated applications use one controller-service lifecycle.
- There is one mutable operational state and one timer/command owner per process.
- FastAPI no longer owns a separate simulator-specific state machine.
- Physical and simulated selection occurs in composition, not domain logic.
- All runtime queues and cross-thread handoffs are bounded and shutdown-clean.
- Current frontend remains operable through documented compatibility behavior.
- Default live composition still cannot transmit or drive physical steering.
- Focused and repository-wide coordinator/frontend checks pass.

