# Phase 3: Engine telemetry simulation

## Goal

Add RPM, oil temperature and coolant temperature to the hardware-independent application snapshot
and drive them through unmistakably simulation-only CAN frames. Each signal can be set and silenced
independently from `/dev`, and stale or never-observed values remain explicit.

This phase does not add or guess BMW identifiers.

## Application state and events

Add immutable samples for RPM, oil temperature and coolant temperature. Each sample contains:

- Canonical numeric value.
- Monotonic observation time.
- Source `CanNetwork`.

Add application events:

- `EngineRpmObserved`
- `OilTemperatureObserved`
- `CoolantTemperatureObserved`

Add optional samples to `ApplicationState` plus a monotonic engine-telemetry evaluation time. The
transition for each observation stores that sample. `ControlTimerElapsed` advances evaluation time
without moving backward.

Add typed configuration for a fixed one-second engine-telemetry timeout. Keep it separate from the
steering speed timeout even though both initially equal one second.

## Snapshot contract

Add `application.engine`:

```json
{
  "rpm": {"value": 3500, "status": "valid"},
  "oil_temperature_c": {"value": 112.5, "status": "valid"},
  "coolant_temperature_c": {"value": null, "status": "stale"}
}
```

Status is exactly:

```text
valid | never_observed | stale
```

Projection rules:

- No sample: `never_observed`, value `null`.
- Sample within timeout: `valid`, value present.
- Sample beyond timeout: `stale`, value `null`.
- Retain the last sample internally for transition history, but do not serialize it as a current
  usable value.
- Existing speed projection remains unchanged for compatibility.

## Simulation-only CAN protocol

Reserve three extended identifiers adjacent to the existing unmistakably synthetic speed ID. Name
them as simulation-only constants and document that they are not BMW candidates.

- RPM frame on PT-CAN.
- Oil-temperature frame on PT-CAN.
- Coolant-temperature frame on PT-CAN.

Use one signal per frame so silence is independent.

Encoding contract:

- RPM is an unsigned integer in `0..12000`, encoded in the smallest clear fixed-width payload.
- Temperature is signed tenths of a degree Celsius in `-40.0..250.0`.
- Frame DLC must match exactly.
- Frames must be extended and received on PT-CAN.
- Encoders reject non-finite, boolean and out-of-range inputs.
- Decoders reject malformed payloads rather than clamping.

Extend `SimulationProtocolRouter.decode` after the normal router has declined the frame. The live
`ProtocolRouter` must continue to ignore all three identifiers.

## Simulated vehicle and engine ownership

Extend `SimulatedVehicleNode` with optional current values:

- `rpm`
- `oil_temperature_c`
- `coolant_temperature_c`

For every signal provide set, emit and silence behavior:

- Set validates through the encoder, stores the canonical value and immediately sends one frame.
- Each control-timer tick emits every non-silenced signal before kernel input draining.
- Silence clears only the selected stored value and sends no fabricated invalid frame.
- Repeated silence is idempotent.
- Simulation reset reconstructs the vehicle and returns all signals to never-observed.

Ensure engine frames use the same in-memory topology, trace and kernel drain path as simulated
speed. Do not update application state directly from an HTTP handler.

## Simulation commands and API

Add closed simulation command values for setting and silencing each signal. Include them in the
engine's exhaustive command match and normal slim-snapshot response path.

Endpoints:

```text
PUT  /api/dev/simulation/vehicle/rpm
POST /api/dev/simulation/vehicle/rpm/silence
PUT  /api/dev/simulation/vehicle/oil-temperature
POST /api/dev/simulation/vehicle/oil-temperature/silence
PUT  /api/dev/simulation/vehicle/coolant-temperature
POST /api/dev/simulation/vehicle/coolant-temperature/silence
```

Bodies:

```json
{"rpm": 3500}
{"temperature_c": 110.0}
```

Pydantic rejects unknown fields. Domain/protocol validation maps to the current 422 API contract.
Every success returns the complete slim snapshot, including all three telemetry projections.

## Frontend types and development controls

Extend simulator snapshot types and the empty placeholder snapshot with the complete engine shape.
Placeholder values use `null` and `never_observed`, never numeric zero.

Add typed API functions for all six commands. Extend the existing simulated-vehicle card rather
than adding unrelated top-level panels:

- RPM control with initial UI range `0..9000`, step 100.
- Oil-temperature control with initial UI range `-40..200` C, step 1.
- Coolant-temperature control with the same initial range.
- Set and Silence for each signal.
- Current Valid, Never observed or Stale status.

The wider backend ranges remain authoritative. Preserve the current speed controls, command
pending guards, responsive layout and error reporting.

## Tests

Application:

- Each event stores value, time and PT-CAN source.
- Evaluation time remains monotonic.
- Exact timeout boundary remains valid; beyond it is stale.
- Signals age independently.
- Never-observed and stale projections contain `null`.

Protocol:

- Boundary and representative values round-trip exactly at defined resolution.
- Signed negative temperatures decode correctly.
- Wrong network, standard frame, wrong DLC and out-of-range values fail as specified.
- Live router does not decode synthetic engine frames.

Simulation/API:

- Set emits a trace frame and valid application value.
- Timer re-emits active signals.
- Silence stops only the selected signal.
- Time advance after silence produces stale while other signals remain valid.
- Reset returns all to never-observed.
- Snapshot HTTP and initial/reconnect WebSocket shapes include engine telemetry.
- Invalid request values return 422 without changing state.

Frontend:

- Empty snapshot is never a plausible zero reading.
- API functions send exact bodies and paths.
- Controls call the correct Set/Silence commands and reflect independent status.
- Existing speed-control component tests remain valid.

## Completion criteria

- All three values travel through the normal simulated CAN and application pipeline.
- They are independently controllable, traceable and ageable.
- Snapshot consumers can distinguish valid, never-observed and stale states.
- No production identifier, decoder or live hardware claim is introduced.
- The development workbench can deterministically create every telemetry validity state needed by
  later car-screen tests.
