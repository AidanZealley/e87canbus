# Phase 8 — Verified Steering Failsafe

## Status

**Blocked until verified evidence exists.** Do not start this phase merely because phases 1–7 are
complete.

## Required evidence

Record all of the following before implementation:

1. Verified BMW speed arbitration ID, source network, payload scaling, update cadence, counters,
   validity bits, and behavior at standstill/fault.
2. Verified actuator boundary: PWM/current driver or steering-controller wire protocol, electrical
   safe state, command range, update cadence, and behavior when commands stop.
3. An agreed safe target current for never-seen speed, stale speed, ingress overflow, reader loss,
   malformed speed traffic, and process shutdown.
4. A hardware watchdog or actuator-controller timeout that enters the electrical safe state when
   coordinator commands stop. Software queue handling is not a substitute for this.
5. Collision validation and an explicit live TX grant for every CAN ID the feature would transmit.

Store captures and conclusions in `docs/candump_sessions/` and `docs/decoded_messages.md`; remove any
corresponding value from `PlaceholderBmwIds` only after verification.

## Goal

Complete the original safety contract: verified speed input drives an explicit steering-current
effect, and loss or untrustworthiness of that input produces a safe command within a bounded time.

## Design

- Add the verified speed decoder to the network-and-ID router. It emits `SpeedObserved` with the
  ingress `received_at` timestamp; decoder processing time is never used for freshness.
- Add the verified actuator effect, for example `SetSteeringCurrent(target_ma, reason)`, only after
  the adapter/protocol is known.
- A control-timer transition calculates Auto assistance from the verified speed sample and the
  existing tested interpolation math.
- Manual and maximum-assistance states calculate their configured targets through the same
  transition path.
- Never-observed or stale speed in Auto, ingress overflow, speed-network reader failure, malformed
  verified speed traffic beyond an explicit threshold, and shutdown all select the agreed safe
  target with a diagnostic reason.
- The effect executor applies clamping and output authorization but does not choose the target; the
  application transition owns that decision.
- Repeated idempotent actuator refreshes have a policy separate from cosmetic LED rate limiting and
  must satisfy the hardware watchdog cadence.

## Simulation

- Add a simulated vehicle node that emits the verified speed CAN frame on the correct network.
- Speed changes and bus silence are controlled through the simulated device, never an application
  injection API.
- Add a simulated actuator endpoint that records verified commands and models command timeout.
- Use the shared fake clock to test silence and overload without real sleeps.

## Required scenarios

1. No speed has ever been observed: safe target is commanded.
2. Fresh speed in Auto: the expected interpolated target is commanded.
3. Speed becomes stale: safe target is commanded no later than one control interval after timeout.
4. A delayed queued speed frame retains its old observation time and cannot clear the failsafe.
5. Fresh verified speed resumes: recovery follows an explicit documented rule and does not oscillate.
6. Speed reader fails or ingress overflows: safe target precedes coordinator shutdown.
7. Manual and maximum-assistance behavior remains bounded and documented when speed is absent.
8. Actuator commands stop: the hardware/simulated watchdog enters the electrical safe state.
9. Live default configuration still has no TX capability; the feature works live only under an
   explicit validated deployment configuration.

## Road-test gate

Before any in-car actuation:

- run all deterministic failure scenarios;
- verify generated protocol artifacts;
- validate kernel/hardware listen-only on networks not explicitly writable;
- bench-test queue overflow, reader disconnect, process kill, and actuator watchdog behavior;
- capture actual command cadence and confirm the network window plus the verified actuator refresh
  policy; and
- document a physical bypass/recovery procedure.

## Acceptance criteria

- Every unsafe input state maps to one explicit safe actuator effect and diagnostic reason.
- Observation timestamps, not processing timestamps, govern freshness.
- Simulator tests use real encoded CAN frames and the production kernel/effect path.
- The hardware watchdog independently handles coordinator silence.
- No placeholder ID or speculative payload appears in executable code.
- All project, frontend, firmware, and bench checks pass.
