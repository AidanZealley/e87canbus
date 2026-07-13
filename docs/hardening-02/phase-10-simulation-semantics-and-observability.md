# Phase 10 — Simulation Semantics and Observability

## Goal

Make the simulated vehicle and steering controller behave as their names imply and expose their
state clearly in the browser workbench. Preserve the simulator-only boundary and the production
input → decode → transition → commit → effect path.

This phase improves the model and its presentation. It does not define physical current, controller
transport, acknowledgement, measured feedback, or an electrical safe state.

## Persistent simulated vehicle speed

`SetVehicleSpeed` must set state on `SimulatedVehicleNode`, not merely emit one anonymous sample.

- Store `speed_kph: float | None` on the external simulated vehicle.
- Setting speed validates it and emits an immediate synthetic F-CAN frame.
- While speed is selected, the simulation scheduler emits it at a documented synthetic cadence. The
  smallest acceptable implementation is to emit immediately before each queued control timer, then
  drain that frame through the kernel before dispatching the timer.
- Add `SilenceVehicleSpeed`; it clears the selected speed so subsequent vehicle cadences emit
  nothing.
- Speed frames remain unrestricted external-device traffic. They do not consume the coordinator TX
  budget.
- The API controls only the external simulated vehicle. It must not construct `SpeedObserved`,
  mutate `ApplicationState`, or call a special application tick.

If implementation evidence shows that a one-shot sample is preferable, record that deviation and
rename the command/API to `EmitVehicleSpeedSample`. Do not keep a `SetVehicleSpeed` name for
one-shot behavior.

## Explicit controller projection

Keep the steering controller an ideal dimensionless model, but name its observable fields so they
cannot be mistaken for measured physical feedback.

- Continue to expose effective simulated assistance in the range `0.0..1.0`.
- Rename the ambiguous `reason` field to `last_command_reason` because watchdog fallback does not
  change the reason attached to the last command.
- Keep `watchdog_timed_out` explicit. When timed out, effective simulated assistance is zero while
  the last command remains available for diagnosis.
- Do not add acknowledgement, current, PWM, position, torque, hydraulic pressure, or measured-output
  fields without a defined simulation contract.

The model may equate a fresh command with effective simulated assistance. Documentation and UI must
call that a simulation projection, never feedback or achieved physical output.

## Diagnostic reasons

Make fallback reasons specific enough to distinguish the required deterministic scenarios. At
minimum distinguish:

- speed never observed;
- speed stale;
- CAN reader failure;
- inbox overflow;
- shutdown; and
- steering actuator execution failure in runtime diagnostics.

Keep target selection in the pure application transition. The kernel maps concrete runtime fault
inputs to explicit fallback requests; the executor does not choose targets or reasons. Avoid enum
conversion based only on coincidentally equal string values—use one valid shared value shape or an
explicit mapping.

## Frontend observability

Add the controller projection to the frontend snapshot contract and existing steering-status UI:

- effective simulated assistance, clearly labelled dimensionless or as a percentage;
- last command reason; and
- watchdog state.

Update `emptySnapshot`, TypeScript types, reducer fixtures, and component tests as required. Reuse
the existing snapshot/reducer path; do not create a separate steering WebSocket event stream.

The frontend remains observational. It is never part of the steering control or watchdog loop.

## Tests

- `SetVehicleSpeed` stores and immediately emits the selected speed through encoded synthetic CAN.
- Repeated control timers emit fresh external speed frames while speed is selected.
- `SilenceVehicleSpeed` stops those frames; Auto becomes stale no later than one control interval
  after the configured timeout.
- Setting speed again recovers Auto on the next ordered timer without direct domain injection.
- Manual and maximum assistance remain bounded and independent of speed availability.
- Watchdog timeout derives zero effective simulated assistance while preserving
  `last_command_reason`.
- API speed and silence endpoints enqueue simulation commands and return revisioned snapshots.
- Frontend types and rendering show controller assistance, last command reason, and watchdog status.
- Reset clears selected vehicle speed and restores the initial controller projection in a new
  session.
- Trace ordering, capacity, session identity, and slim-snapshot behavior remain unchanged.

## Simplicity constraints

- `SimulatedVehicleNode` owns selected vehicle speed; do not duplicate it in the API, engine, or
  application state.
- Use the existing control-timer scheduling operation rather than adding a second scheduler unless a
  separate cadence is required by a demonstrated test.
- Extend the existing snapshot and steering panel rather than adding a new frontend store or event
  channel.
- Do not model a physical control loop, actuator dynamics, or feedback that has not been specified.
- Do not restore the reactive-device quiescence loop: the current vehicle emits on a composition
  schedule and the controller remains a direct capability. Phase 11 records the gate for future
  reactive CAN devices.

## Acceptance criteria

- Vehicle “set speed” semantics are persistent and bus silence is explicit, or the API is honestly
  renamed as one-shot emission with the deviation recorded.
- All speed observations still originate as encoded frames from an external simulated node.
- Controller snapshot names distinguish effective simulation state from last command metadata.
- Required fallback scenarios have distinct diagnostic reasons.
- The browser displays the simulated controller projection without joining the control loop.
- No simulated ID, router, actuator capability, or value is composed into live execution.
- Backend and frontend checks pass.
