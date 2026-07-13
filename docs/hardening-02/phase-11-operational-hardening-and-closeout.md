# Phase 11 — Operational Hardening and Closeout

## Goal

Close the remaining bounded operational risks around simulator publication, configuration, and live
cleanup, then perform a final Hardening 02 architecture and simplicity audit.

This phase adds no feature behavior and no vehicle or actuator protocol.

## Bounded WebSocket publication

A connected peer that never completes a send must not hold the publication lock and simulation owner
indefinitely.

- Add one positive configurable WebSocket send timeout under simulation configuration.
- Apply it to the initial snapshot send and normal event publication.
- On timeout or send failure, log and remove only that peer, then continue to healthy peers.
- Preserve operation order: do not launch detached per-operation broadcasts or allow later snapshots
  to overtake earlier frames.
- Keep the command queue bounded. A temporarily slow peer may delay an operation only up to the
  configured timeout.

Use `asyncio.timeout()` or the smallest equivalent supported by the project Python version. Do not
add a connection worker/task per peer unless the timeout approach is proven insufficient.

## Configuration validation

Validate every scheduling/timeout value used by this pass at construction:

- `tick_interval_s > 0`;
- WebSocket send timeout is positive; and
- existing queue capacities, speed timeout, TX window, and simulated watchdog constraints remain
  enforced.

Do not add a generic validation framework. Keep checks in the relevant frozen dataclass
`__post_init__` methods.

## Bounded adapter cleanup

SocketCAN shutdown errors must not mask the original startup/runtime result or prevent remaining
interfaces from closing.

- Catch normalized `OSError` independently for each bus during partial-open cleanup and final
  shutdown.
- Log the interface and error, continue closing the remaining buses, and retain the original non-zero
  result when one already exists.
- Consolidate duplicated cleanup in one small helper only if it makes both paths clearer.
- Preserve bounded reader joins and non-interactive shutdown.

## Simulation-only composition guard

Strengthen the inexpensive architecture tests so the simulation speed protocol and steering
capability cannot drift into live composition unnoticed.

- Production modules outside the simulation boundary must not import
  `SimulationProtocolRouter`, its synthetic speed constants/codecs, or simulated device classes.
- Explicitly allow the simulator API/CLI to import the simulation engine as composition, without
  allowing them to construct application events or state.
- Default live configuration still grants no CAN TX and `run_live` still supplies no steering
  actuator.

Use the existing standard-library AST/source guards. Do not add an architecture-testing dependency.

## Reactive-device gate

Do not restore a generic cascade loop in this phase. Document this binding rule in the simulation
architecture:

> Before the first simulated device can emit a CAN response while processing an incoming CAN frame,
> `SimulationEngine` must regain a bounded run-until-quiescent loop with an explicit livelock cap and
> deterministic tests.

The current direct steering capability, scheduled vehicle emission, and passive NeoTrellis LED sink
must continue to settle in one visible pass. Adding unused cascade machinery would violate the
minimal-code goal.

## Final simplification audit

Review every production file changed by phases 8–11 and remove:

- duplicate revision, selected-speed, controller-projection, or fault state;
- obsolete open/closed-loop, current, PWM, or physical-safe-state language;
- optional fields used as implicit type tags;
- direct simulator access to kernel/application mutation;
- stale aliases, compatibility helpers, and tests coupled to public mutable internals;
- redundant snapshot/event paths; and
- comments that narrate code instead of recording safety or ordering constraints.

Keep `SimulationEngine` as a software term only if its documentation makes that unambiguous in this
automotive repository. If confusion remains, a rename to `Simulator` or `SimulationRunner` is
allowed only when it is a complete mechanical replacement with no compatibility alias.

## Tests

- A WebSocket whose send never completes is removed within bounded test time.
- A stalled peer cannot prevent a healthy peer from receiving the same ordered publication.
- Initial snapshot send is also bounded.
- Zero/negative tick and WebSocket timeout configuration is rejected.
- One SocketCAN shutdown failure does not prevent other interfaces from closing or mask an existing
  failure result.
- Architecture guards reject simulation protocol/device imports from live composition.
- Default live startup still sends no frames.
- Existing command-queue overflow, publication ordering, trace reduction, TX budget, reader failure,
  actuator failure, watchdog, speed silence, and recovery tests remain passing.

## Checks

Run the complete repository closeout suite, whether or not every area changed in this phase:

```bash
uv run pytest -q
uv run mypy
uv run ruff check coordinator
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh
cd frontend && pnpm typecheck && pnpm lint && pnpm test
```

Run firmware builds only if firmware or its generated inputs changed. Do not claim physical actuator
or bench verification when no verified hardware boundary exists.

## Acceptance criteria

- WebSocket publication and initial connection have a finite failure bound and retain ordering.
- Scheduling configuration cannot create a zero-delay busy loop.
- Adapter cleanup is per-interface, bounded, and error-isolated.
- CI-visible guards keep all simulation-only steering/speed definitions out of live composition.
- The reactive-device quiescence prerequisite is explicit without unused implementation.
- Documentation consistently describes simulator-only assistance and preserves all physical evidence
  gates.
- The final implementation has one ordered input path, one state/revision owner, one effect exit, and
  no superseded compatibility path.
- All closeout checks pass.
