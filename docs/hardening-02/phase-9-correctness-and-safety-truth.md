# Phase 9 — Correctness and Safety Truth

## Goal

Remove stale physical steering claims and close the two event-kernel correctness gaps found after
the simulator-only Phase 8 rewrite: time must never move backwards, and a fatal output failure must
not leave the simulator running normally.

This phase changes no steering policy, simulated assistance curve, vehicle protocol, or physical
integration. It makes the existing reduced scope truthful and internally consistent.

## Evidence hygiene

Rewrite the steering section of `PROJECT_CONTEXT.md` so it distinguishes the desired vehicle
behavior from facts that still require evidence.

- Retain the product goal: speed-sensitive assistance, manual levels, and a temporary maximum
  assistance selection.
- Remove or quarantine every unverified assertion about solenoid current direction, example current
  values, resistance, driver IC selection, PWM topology, electrical fallback, and whether the Pi or a
  separate controller drives the output.
- State explicitly that command transport, current range and polarity, valve behavior, feedback,
  electrical safe state, and watchdog behavior remain unknown.
- Keep candidate BMW IDs visibly provisional and non-executable.
- Reconcile any root, coordinator, simulation, and hardening documentation made inconsistent by the
  correction. Do not preserve unsafe guidance merely as historical prose in an authoritative
  context document.

If old research notes are worth retaining, move them under an unmistakable `Unverified research`
heading. They must not read as implementation instructions or default values.

## Monotonic control time

Both speed observations and control timers must preserve a monotonically non-decreasing
`speed_evaluated_at` value:

```python
speed_evaluated_at = max(state.speed_evaluated_at, incoming_time)
```

A delayed frame or regressing timer timestamp must never make a stale sample fresh again. Preserve
the distinction between ingress observation time and evaluation time; do not replace either with an
ambient clock read.

## Typed output failures

Replace `EffectFailure(network: CanNetwork | None)` and the corresponding optional-network runtime
input with an explicit closed union. Use small frozen values such as:

- `CanEffectFailure(network, message)` / `CanEffectExecutionFailed(network, failed_at, message)`;
- `SteeringActuatorFailure(message)` / `SteeringActuatorFailed(failed_at, message)`.

Names may follow neighboring style, but `None` must no longer act as a hidden failure-type tag. The
executor decides only whether I/O succeeded. The composition converts failures into later kernel
inputs; effect execution must not recursively re-enter the kernel.

Handle the closed application-effect, execution-failure, and kernel-input unions explicitly. End
exhaustive branches with `typing.assert_never()` where it makes a future union addition fail type
checking instead of falling into an unrelated case.

## Fatal simulator behavior

The simulator must treat fatal kernel health as a terminal session condition, not a diagnostic bit
that it ignores.

- Feed each execution failure back through the kernel's ordered input path after the originating
  commit has completed.
- Do not accept another normal simulation command after fatal health is recorded. Reset may create a
  fresh session.
- Apply the same bounded shutdown rule as live composition: attempt the committed fallback/shutdown
  effects once, do not retry a failed actuator recursively, and retain the original fault.
- Make the fault observable to the caller and simulator snapshot or diagnostic response. Do not
  return an apparently healthy successful operation after an actuator failure.
- Delete `SimulationEngine._revision`. The kernel owns revision; simulator publication reads it from
  the kernel's committed diagnostics.

Use a small direct control-flow helper if it removes duplicated commit/failure handling. Do not add
a generic event dispatcher, callback registry, or shared framework between live and simulation.

## Tests

- A timer timestamp older than the current evaluation time cannot make stale speed valid.
- A delayed old speed frame remains stale after a later timer.
- CAN and steering-actuator failures are distinct values with no optional network discriminator.
- A failing simulated actuator records fatal actuator health and cannot be followed by a successful
  timer/button command in the same session.
- Reset after a fatal simulator fault creates a healthy new session at kernel revision one.
- Kernel and published simulator revisions cannot diverge, including failure and reset paths.
- A failure while attempting shutdown/fallback is bounded and cannot recurse or loop.
- Live effect failures still exit non-zero and reader/overflow faults still apply their fallback
  before shutdown.
- Architecture/type tests reject an unhandled new event, effect, or failure variant where practical.

## Simplicity constraints

- Prefer two explicit failure dataclasses over an inheritance hierarchy.
- Keep one authoritative revision and one fatal-health value.
- Do not introduce an engine state machine if a boolean/enum already owned by kernel diagnostics can
  enforce the terminal condition.
- Delete tests that mutate public simulator internals when the same behavior can be tested through a
  command, a supplied capability, or a read-only diagnostic.
- This phase does not add frontend controls, persistent simulated speed, WebSocket policy, a CAN
  actuator protocol, or physical values.

## Acceptance criteria

- Authoritative documentation contains no unsupported current, polarity, resistance, driver, PWM,
  safe-state, or controller-topology claim.
- Speed evaluation time cannot regress through either observation or timer events.
- Output failure type is explicit; no optional network field distinguishes actuator from CAN failure.
- Fatal simulator health stops normal command processing and is observable.
- Kernel revision is the only revision source.
- Live and simulated failures retain commit-before-effect order and bounded shutdown.
- Backend checks pass, and documentation agrees with the simulator-only Phase 8 evidence gate.
