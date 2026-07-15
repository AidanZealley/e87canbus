# Unified controller architecture roadmap

This directory specifies the phased migration from the separate live CAN runner and simulator API
to one controller application with replaceable physical and simulated adapters. It is the source of
truth for the approved architecture, sequencing, ownership boundaries, public contracts and
verification requirements.

The roadmap optimizes for the lowest practical complexity that still provides deterministic
control, bounded resource use, honest simulation, safe output and a performant frontend. It does
not grant authority for unverified BMW decoding, physical steering output or live CAN
transmission.

## Product outcome

One supervised process on the Pi will own:

- K-CAN, PT-CAN and F-CAN ingestion through selected adapters.
- One bounded, ordered controller input path and one owner of operational state.
- Pure state transitions that return immutable snapshots and explicit effects.
- Capability-controlled CAN and steering outputs.
- FastAPI resources and commands, Socket.IO live-state publication and SQLite persistence.
- Physical, emulated or observer composition for repository-owned custom devices.
- A deliberately narrow simulated vehicle signal source rather than a model of the whole car.

The React application will use:

- One `socket.io-client` connection outside React.
- Zustand for current live controller state and a separate bounded diagnostic trace.
- TanStack Query for HTTP resources, mutations and their local pending/error state.
- Narrow selectors and topic updates so adjacent telemetry or commands do not rerender or fade an
  entire panel.

## Approved architecture

```text
SocketCAN / virtual CAN / HTTP / clock
                  |
                  v
        bounded controller inbox
                  |
                  v
     protocol decode + controller core
                  |
                  v
   commit(snapshot, revisions, effects)
          |                    |
          v                    v
 capability effect       coalescing live-state
    execution                 publisher
          |                    |
          v                    v
 real/emulated devices     Socket.IO -> Zustand

 SQLite <-> HTTP resources/mutations <-> TanStack Query
```

The core does not import FastAPI, Socket.IO, SQLite, React or simulator controls. Adapters may be
replaced, but no adapter may mutate operational state directly.

## Fixed decisions

- Deploy one modular Python application, not microservices or separate live/simulator backends.
- Retain a bounded single-owner controller path as the only operational-state mutation boundary.
- Keep protocol bytes and CAN identifiers outside domain transitions.
- Represent each accepted transition as a commit with a process `boot_id`, monotonic revision,
  immutable snapshot, changed topics and ordered effects.
- Use HTTP for business commands and durable-resource CRUD.
- Use one Socket.IO namespace for server-to-browser live-state replication. Socket client events
  may control transport subscriptions such as diagnostic trace, but are not business commands.
- Send a complete current snapshot after every new or unrecoverable socket connection. Do not
  build durable telemetry replay.
- Process relevant controller inputs at their required cadence while coalescing browser telemetry
  to a bounded latest-state rate.
- Keep every inbox, publication queue, trace and retained history bounded.
- Keep SQLite limited to durable desired configuration. Do not persist live telemetry or socket
  traffic.
- Use explicit, idempotent commands such as `SetMaximumAssistance(true)`, never ambiguous toggles.
- Permit exactly one ingress authority per device capability. Read-only observers may mirror state.
- A physical custom device and its emulator use the same wire codec and controller path.
- Dashboard control uses semantic controller commands by default. Device-development controls may
  deliberately operate an emulator through its real wire protocol.
- Model desired and observed device state separately. Never claim an observation when the device
  protocol supplies no acknowledgement.
- Simulate only vehicle signals consumed by this project. Until real BMW definitions are verified,
  synthetic identifiers remain visibly simulation-only and excluded from the live router.
- Default live composition remains unable to transmit. Every real output capability is an
  evidence-gated, deny-by-default grant.
- Do not implement the proposed steering-controller profile ownership in ADR 0007 unless that ADR
  is separately accepted and its hardware evidence gates are satisfied.

## Phases

| Phase | Document | Outcome | Depends on |
|---:|---|---|---|
| 1 | [Runtime contracts](01-runtime-contracts.md) | Accepted architecture record, stable input/commit/publication contracts and regression baseline | Current repository |
| 2 | [Unified composition](02-unified-composition.md) | One lifecycle and controller service usable with live or simulated adapters | Phase 1 |
| 3 | [Commands and resources](03-commands-and-resources.md) | Typed HTTP command gateway, idempotent operational commands and precise durable resources | Phase 2 |
| 4 | [Socket.IO state publication](04-socketio-state-publication.md) | Fixed live topics, reconnect snapshot, revisions, coalescing and bounded trace delivery | Phases 1-3 |
| 5 | [Frontend data ownership](05-frontend-data-ownership.md) | Socket.IO-to-Zustand live path and TanStack Query-only HTTP ownership | Phase 4 |
| 6 | [Simulation and device convergence](06-simulation-and-device-convergence.md) | Physical/emulated/observer adapters on the same controller pathways | Phases 2-5 |
| 7 | [Reliability and deployment](07-reliability-and-deployment.md) | Explicit failure policy, health, bounded diagnostics, shutdown and supervised service | Phases 2-6 |
| 8 | [Cutover and acceptance](08-cutover-and-acceptance.md) | Legacy-path removal, repository verification, reconnect/failure testing and frontend soak evidence | Phases 1-7 |

Phases are intentionally sequential because they share the controller composition and public data
contracts. A smaller slice inside one phase is allowed, but an implementation agent must record the
slice and leave the phase below `Verified` until every criterion is satisfied.

## Cross-phase data flows

### Physical CAN observation

```text
SocketCAN reader
  -> timestamped RoutedCanFrame
  -> bounded inbox
  -> production protocol decoder
  -> domain event
  -> controller transition and commit
  -> changed live topic
  -> Socket.IO
  -> Zustand slice
  -> narrow React selector
```

### Dashboard operational command

```text
TanStack mutation
  -> HTTP semantic command
  -> validation
  -> bounded controller inbox
  -> controller transition and commit
  -> command acknowledgement
  -> effects to physical/emulated capabilities
  -> Socket.IO authoritative state
  -> Zustand
```

The command response acknowledges processing; it does not force a complete vehicle refetch.

### Durable resource mutation

```text
TanStack mutation
  -> HTTP resource update with expected revision
  -> domain validation
  -> short SQLite transaction
  -> runtime configuration input when relevant
  -> updated resource response
  -> exact Query cache replacement
  -> precise resources.changed event for other clients
```

SQLite transactions never span controller waits, effect execution or socket publication.

### Emulated custom device

```text
Device-development interaction
  -> emulated device
  -> repository-owned CAN encoder
  -> virtual bus
  -> normal ingress/decoder/core path
  -> normal CAN effect
  -> virtual bus
  -> emulated device decoder
```

When the physical device is selected, the dashboard representation reads canonical controller
state and cannot emit duplicate device-originated traffic.

### Narrow simulated vehicle signal

```text
Development signal control
  -> simulated vehicle signal source
  -> simulation-only CAN frame until a real definition is verified
  -> virtual network
  -> normal ingress timestamping and controller path
```

The simulator does not update application state from an HTTP handler and does not attempt to model
unrelated vehicle behavior.

## Public contract direction

Exact shapes are finalized in their owning phases. The approved direction is:

```text
HTTP
  /api/settings
  /api/steering/profiles
  /api/commands/maximum-assistance
  /api/commands/steering-mode
  /api/commands/activate-steering-profile
  /api/dev/simulation/*                 development composition only

Socket.IO server events
  controller.snapshot
  vehicle.state
  engine.state
  steering.state
  buttons.state
  devices.state
  controller.health
  resources.changed
  trace.batch                           opt-in only
```

Pydantic models remain the backend source for HTTP and socket payload schemas. Generated
TypeScript contracts are preferred where they remove duplication without introducing a separate
schema platform.

## Compatibility and cutover policy

- Existing HTTP and WebSocket behavior may be retained temporarily when a phase needs it to keep
  the current frontend operational.
- Compatibility paths must be clearly marked, covered and assigned a removal phase.
- No new feature may target a legacy path.
- Phase 5 switches the frontend to the new ownership model.
- Phase 8 removes the legacy raw WebSocket/snapshot-cache path and separate simulator-only
  composition after all consumers have moved.
- CLI aliases may remain when they are harmless operator compatibility wrappers around the same
  composition; they must not construct a second architecture.

## Working method

Give an implementation agent one phase at a time using
[phase-agent-prompt.md](phase-agent-prompt.md). Agents must inspect current code and the existing
implementation log before changing anything because phase documents describe required outcomes,
not permission to overwrite newer work.

After a phase or meaningful slice, append a factual entry to
[implementation-log.md](implementation-log.md). Do not mark a phase `Verified` because focused
tests alone pass. Verification requires all completion criteria, relevant repository-wide checks
and any browser, soak or adapter evidence specified by the phase.

## Global non-goals

- A generic internal event bus, broker, CQRS framework or event-sourced database.
- Redis, MQTT, Kafka, NATS or multi-process fan-out.
- A complete digital twin of the BMW.
- Durable replay of every CAN or Socket.IO event.
- Guessed BMW identifiers, cadence, counters, checksums or fallback behavior.
- Enabling real CAN transmission merely to prove software composition.
- Invented real-device heartbeat, acknowledgement or health semantics.
- Physical Servotronic transport, safe-state or watchdog claims without required evidence.
- Implementing ADR 0007's proposed physical controller protocol as part of this roadmap.
- Persisting transient telemetry, connection state or frontend drafts in SQLite.
- Putting live telemetry in TanStack Query or durable resources in Zustand.
- Socket listeners owned by React components.
- Whole-page loading/fade behavior for local mutations.
- Unbounded trace retention or performance instrumentation workarounds that change the developer
  environment instead of fixing data flow.
