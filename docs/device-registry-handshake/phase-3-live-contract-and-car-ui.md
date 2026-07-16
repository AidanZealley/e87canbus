# Phase 3 — Live contract and `/car` UI

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Agent prompt](phase-agent-prompt.md) ·
[Previous phase](phase-2-kernel-registry-and-gating.md) ·
[Next phase](phase-4-simulation-and-dev-ui.md)

## 1. Objective

Replace the broad device projection with the fixed registry contract, move
Servotronic observations into the steering topic, and make `/car` communicate
optional-device availability precisely without creating global failure UI.

## 2. Dependencies and starting state

- Phases 1 and 2 must be completed in the implementation log.
- The kernel registry and server-side availability rules are authoritative.
- The live contract is unreleased version 1 and may be updated in place, but
  backend and frontend changes must land together.
- Frontend instructions in `frontend/AGENTS.md` apply.

## 3. In scope

- Registry-oriented service and Pydantic projections.
- Generated live v1 schema and TypeScript transport types.
- Moving actuator observation to `steering.servotronic`.
- Removing desired/observed LED duplication from public state.
- Reference-preserving frontend store application.
- `/car` footer visibility and dependent-screen explanations.
- Mapping unavailable domain errors to HTTP 409.
- Contract, store, render, route, and API tests.

## 4. Explicitly out of scope

- `/dev` lifecycle controls and reusable simulated-device cards.
- Virtual device state machines.
- Firmware.
- Live protocol v2 or dual-protocol support.
- A physical Servotronic telemetry protocol.

## 5. Required implementation changes

1. Remove `DeviceProjection` and adapter-owned desired/observed LED fields from
   the service snapshot.
2. Project the fixed registry role map plus the existing network collection in
   `devices.state`.
3. Add nullable Servotronic actuator observation to `SteeringState` and remove
   `devices.steering_controller`.
4. Rename health/model fields that refer to the optional actuator while
   retaining application-level steering names.
5. Project `buttons.led_colours` only from the canonical controller state.
6. Map the phase 2 unavailable exception to HTTP `409` with stable code
   `feature_unavailable` and a status-specific message.
7. Regenerate `protocol/live-events-v1.schema.json` and update explicit
   TypeScript event types without changing `LIVE_PROTOCOL_VERSION`.
8. Change the Zustand store's registry application to reuse each previous role
   entry object when all public fields are equal.
9. Change normal selectors to select one role entry rather than the whole
   devices object when possible.
10. Update the overview footer to omit `disabled` and `not_found`, retain every
    observed status, and present lifecycle-specific text.
11. Make `/car/steering` unavailable with the exact dependency reason unless
    registry and output capability are usable.
12. Show assistance as unavailable on the overview under the same rule.
13. Keep profile repository APIs usable while the device-dependent screen and
    activation actions are unavailable.

## 6. Public interfaces and types

`DevicesState` becomes equivalent to:

```ts
type DeviceRegistryEntry = {
  role: "button_pad" | "servotronic_controller"
  label: string
  device_id: number
  source_mode: "physical" | "emulated" | "disabled"
  status:
    | "disabled"
    | "not_found"
    | "pending"
    | "active"
    | "stale"
    | "incompatible"
    | "fault"
  protocol_version: number | null
  device_session_id: number | null
  last_status_code: number | null
  last_transition_monotonic_s: number | null
}

type DevicesState = {
  registry: {
    button_pad: DeviceRegistryEntry
    servotronic_controller: DeviceRegistryEntry
  }
  networks: NetworkState[]
}
```

`SteeringState` adds:

```ts
servotronic: {
  effective_assistance: number
  last_command_reason: SteeringCommandReason | null
  watchdog_timed_out: boolean
} | null
```

Do not add private session/lease fields or another LED array.

Unavailable responses use:

```text
HTTP 409
error.code = "feature_unavailable"
error.message = a concise specific reason such as
  "servotronic controller is stale"
  "servotronic controller is incompatible"
  "servotronic output adapter is unavailable"
```

## 7. Expected files/modules affected

- `coordinator/src/e87canbus/service.py`
- `coordinator/src/e87canbus/api/models/live.py`
- `coordinator/src/e87canbus/api/internal/live.py`
- `coordinator/src/e87canbus/api/internal/operational_commands.py`
- `coordinator/src/e87canbus/api/errors.py`
- `protocol/live-events-v1.schema.json`
- `scripts/generate_live_contract.py`
- `frontend/src/api/live-events.ts`
- `frontend/src/live/live-store.ts` and fixtures/tests
- `frontend/src/components/device-status-footer/`
- `frontend/src/components/car-overview/`
- `frontend/src/components/car-steering-editor/`
- relevant simulator components temporarily consuming actuator observations
- live-contract, publication, command API, frontend store, and screen tests

## 8. Detailed implementation sequence

1. Change service projections to expose kernel registry state and canonical
   buttons without adapter duplication.
2. Change Pydantic live models and topic serializers.
3. Move Servotronic observation into steering projection and update all backend
   model validation/tests.
4. Implement HTTP 409 translation at the operational use-case boundary.
5. Regenerate and check the live v1 schema.
6. Update TypeScript transport types and empty/snapshot fixtures atomically.
7. Implement entry-by-entry store reconciliation and narrow selectors.
8. Update footer labels/filtering and dependent-screen unavailable views.
9. Ensure profile CRUD queries do not acquire a registry dependency.
10. Run contract, API, store, and UI test suites.

## 9. Edge cases and failure behavior

- A role starts in the map even when `not_found`; normal `/car` UI filters it
  rather than treating absence from JSON as state.
- Once observed, stale/incompatible/fault entries remain visible for the
  controller boot.
- A synchronized Socket.IO connection does not imply device availability.
- An active registry entry with a missing/faulted output adapter still leaves
  steering unavailable and explains the adapter condition.
- A fault status code is displayed as opaque numeric diagnostics, not given an
  invented meaning.
- A heartbeat with no public change must not replace either registry-entry
  reference.
- Old frontend/backend combinations are unsupported; protocol v1 is updated in
  place because no deployment exists.

## 10. Required tests and verification commands

Test:

- exact Pydantic/JSON fields and enum values;
- schema generation freshness;
- controller snapshots and topic events;
- absence of old desired/observed LED fields and `steering_controller`;
- Servotronic observations in the steering topic;
- every unavailable command returning 409/code/message;
- profile CRUD remaining available;
- footer hiding disabled/not-found and retaining all observed statuses;
- exact steering unavailable reasons;
- active registry but unavailable output adapter;
- unchanged button-pad reference during Servotronic-only changes;
- no render caused by ordinary heartbeat traffic.

Run at minimum:

```text
uv run python scripts/generate_live_contract.py --check
uv run pytest coordinator/tests/test_live_contract.py coordinator/tests/test_live_publication.py coordinator/tests/test_socketio_server.py coordinator/tests/test_command_api.py coordinator/tests/test_profile_api.py
cd frontend && pnpm test --run
cd frontend && pnpm build
```

Use the repository's actual package scripts if their names differ; record the
exact commands in the log.

## 11. Exit criteria

- Generated live v1 schema, backend models, and TypeScript types agree.
- No public duplicate LED truth remains.
- The devices topic is registry-oriented and steering owns Servotronic
  observation.
- Normal UI hides never-observed optional devices but explains observed
  failures and feature unavailability.
- Store reference and no-render tests pass.
- Profile storage remains hardware-independent.

## 12. Required implementation-log update

Update the phase 3 row and append a log entry describing schema changes, old
fields removed, HTTP behavior, UI states, reference-preservation work, and all
test/build results. Any temporary simulator adaptations that phase 4 must
replace must be explicit.

## 13. Handoff notes for phase 4

The `/dev` implementation must consume these live registry entries. It must not
add simulation-control state to the production registry contract or directly
assign lifecycle statuses.
