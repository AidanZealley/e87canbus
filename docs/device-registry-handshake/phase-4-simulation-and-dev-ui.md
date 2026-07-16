# Phase 4 — Simulation and `/dev` UI

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Agent prompt](phase-agent-prompt.md) ·
[Previous phase](phase-3-live-contract-and-car-ui.md) ·
[Next phase](phase-5-button-pad-firmware.md)

## 1. Objective

Implement virtual peers that exercise the real protocol and add development
controls that manipulate peer behavior, making every registry scenario
observable end to end without directly mutating registry state.

## 2. Dependencies and starting state

- Phases 1–3 must be completed in the implementation log.
- Registry codecs, kernel lifecycle, live projection, and frontend role types
  are authoritative.
- The simulated runtime already owns an in-memory K-CAN topology, fake-clock
  seams, trace collection, and a virtual NeoTrellis decoder.
- Frontend structure and shadcn rules in `frontend/AGENTS.md` apply.

## 3. In scope

- Virtual button-pad and Servotronic registration state machines.
- Deterministic device scheduling and controller response processing.
- Healthy default startup/reset.
- Connect/disconnect/reboot/version/fault API actions.
- Reusable `SimulatedDeviceCard` with protocol-driven status.
- NeoTrellis and Servotronic workbench integration.
- Trace and lifecycle scenario tests.

## 4. Explicitly out of scope

- Direct registry-state setters.
- UI controls for malformed payloads, sequences, raw frames, or duplicates.
- Compiled Arduino execution in simulation.
- Physical Servotronic output transport.
- Browser-side inference of lifecycle state.

## 5. Required implementation changes

1. Give each virtual peer its own K-CAN endpoint, device session, sequence,
   configured protocol version, status code, and contact timers.
2. Implement the same device-local states and frame validation defined in the
   overview.
3. Process controller acknowledgements from the bus; do not call registry
   methods or use a simulation-only activation signal.
4. Integrate virtual-device deadlines into deterministic runtime processing
   with an explicit bounded drain/fixed-point rule.
5. Start/reset with both devices present, compatible, healthy, and discovering.
6. Ensure the first HELLO can publish pending before the first heartbeat makes
   the role active; tests may inspect each processing step even when UI
   publication coalesces a short transition.
7. Replace the independent simulated steering-controller naming with one
   virtual Servotronic peer associated with the existing in-process actuator.
   Registry availability gates that actuator, but its commands remain
   in-process in this phase.
8. Add strict API commands for peer connect, disconnect, reboot, version, and
   status code.
9. Add a `SimulatedDeviceCard` component using the existing Card and Badge
   primitives. It takes a role/entry, actions, pending flags, and children.
10. Refactor the NeoTrellis and Servotronic panels to render inside that wrapper
    without nested duplicate cards.
11. Show context-sensitive Connect, Disconnect, Reboot, Simulate incompatible,
    Restore compatible, Set fault, and Clear fault actions.

## 6. Public interfaces and types

Add development-only endpoints:

```text
POST /api/dev/simulation/devices/{role}/connect
POST /api/dev/simulation/devices/{role}/disconnect
POST /api/dev/simulation/devices/{role}/reboot
PUT  /api/dev/simulation/devices/{role}/protocol-version
PUT  /api/dev/simulation/devices/{role}/status-code
```

`role` accepts only `button_pad` and `servotronic_controller`.

Requests are strict:

```json
{ "protocol_version": 2 }
{ "status_code": 1 }
```

Both integer fields are bounded to 0–255. Changing version reboots a present
peer so a new `HELLO` advertises it. Status changes apply to subsequent
heartbeats. Connect and disconnect are idempotent. Reboot of an absent peer
returns `409 simulation_device_unavailable`.

The wrapper component's public props should be equivalent to:

```text
role
registryEntry
availableActions / callbacks
pendingAction
children
```

It displays server registry status; it does not own a second lifecycle model.

## 7. Expected files/modules affected

- `coordinator/src/e87canbus/simulation/devices.py`
- `coordinator/src/e87canbus/simulation/runtime.py`
- `coordinator/src/e87canbus/simulation/bus.py` if bounded scheduling needs a
  focused extension
- `coordinator/src/e87canbus/api/models/simulation.py`
- `coordinator/src/e87canbus/api/routes/simulation.py`
- `coordinator/src/e87canbus/api/internal/simulation.py`
- `frontend/src/api/simulator.ts`
- `frontend/src/components/simulator-workbench/`
- new `simulated-device-card/` component directory following frontend naming
  conventions
- simulator API, runtime, device, trace, and UI tests

## 8. Detailed implementation sequence

1. Extract/share a virtual registry-peer state machine used by both roles.
2. Integrate role-specific IDs and device bus endpoints.
3. Add deterministic due-time processing and bounded bus draining.
4. Make reset construct both healthy peers and complete registration through
   frames.
5. Add runtime commands and strict API models/routes.
6. Add client functions and mutation error handling.
7. Implement `SimulatedDeviceCard` with status badge and actions.
8. Refactor the NeoTrellis and Servotronic workbench sections into wrappers.
9. Add fake-clock lifecycle tests, trace assertions, and UI interaction tests.
10. Run full coordinator/frontend regression checks.

## 9. Edge cases and failure behavior

- Disconnect stops all frames immediately; the controller remains active until
  its lease naturally expires.
- Reconnect/Connect creates a new device session and begins with HELLO.
- Reboot while active immediately announces a new session and moves the
  controller through pending before active.
- Incompatible peers retry every five seconds and become stale after the
  controller's 15-second incompatible observation timeout if removed.
- Faulted peers continue heartbeat/ACK contact.
- Controller ACK loss drives the peer through `controller_lost`; do not fake
  that state from UI.
- Reset discards previous peer scenarios and returns to protocol v1/status 0.
- Failed or repeated API actions do not partially update the registry.
- Bus processing has an explicit iteration/frame bound so a responding peer
  cannot create an infinite in-process loop.

## 10. Required tests and verification commands

Test:

- default HELLO → ACK → heartbeat → active traces for both roles;
- pending visibility at a deterministic processing boundary;
- disconnect timeout and stale status;
- reconnect and reboot session changes;
- incompatible response/retry/recovery;
- nonzero fault heartbeat and healthy recovery;
- controller acknowledgement loss and device rediscovery;
- reset restoring healthy defaults;
- strict role/body API validation and absent reboot conflict;
- no direct registry mutation in simulator commands;
- wrapper status labels, context actions, pending states, and error handling;
- NeoTrellis and Servotronic children inside the shared wrapper;
- no wall-clock sleeps.

Run at minimum:

```text
uv run pytest coordinator/tests/test_simulation_devices.py coordinator/tests/test_simulation_runtime.py coordinator/tests/test_simulator_api.py coordinator/tests/test_simulation_protocol.py coordinator/tests/test_simulation_bus.py
cd frontend && pnpm test --run
cd frontend && pnpm build
```

## 11. Exit criteria

- Both simulated roles become active exclusively through encoded CAN traffic.
- All lifecycle actions produce genuine registry transitions and trace rows.
- Reset is deterministic and healthy.
- `/dev` uses one reusable device wrapper and the production registry status.
- Fake-clock, API, trace, UI, and regression tests pass.

## 12. Required implementation-log update

Update the phase 4 row and append an entry covering virtual peer architecture,
scheduler bounds, endpoint semantics, UI component paths, trace evidence, and
all verification results. Record any firmware-relevant behavior phase 5 must
mirror.

## 13. Handoff notes for phase 5

The Arduino implementation must follow the same vectors, state transitions,
and timing. Do not copy simulator-only scheduling or introduce physical LED
claims that the hardware integration does not yet support.
