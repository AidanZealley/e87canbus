# Workstream 3: Retire Servotronic and delete the device-CAN platform

Status: not started.

## Task packet

### Outcome

The coordinator owns desired steering state and curves but no longer calculates, sends, observes or
simulates Servotronic output. The old project-device CAN platform and every type that belongs to it
are gone in the same change.

### Scope

- Delete curve transfer, control and status wire behavior and the Servotronic ISO-TP output path.
- Delete coordinator-side curve evaluation, periodic assistance commands, speed-driven output,
  fallback commands, activation acknowledgement and observed applied state.
- Delete steering actuator and device-adapter failures that exist only for Servotronic execution.
- Remove registry and adapter availability checks from steering commands, curve activation and
  button active-state presentation.
- Preserve desired steering mode, manual level, maximum override, active curve/profile selection and
  their persistence and HTTP operations.
- Keep vehicle speed as browser telemetry while separating it from steering output decisions.
- Delete the old firmware, simulated Servotronic peer, watchdog and applied-output UI.
- Remove calculations, projections, tests and dependencies with no consumer after this deletion.
- Delete `protocol/custom.toml`, generated custom protocol output and documentation, its generator
  script and CI drift check.
- Delete registry discovery, heartbeat, acknowledgement, device sessions, lifecycle state,
  catalogue metadata and registry diagnostics.
- Delete `DeviceRole`, `DeviceSource` and project-device deployment choices. Slice 02 owns any new
  role identity type.
- Delete Python and embedded ISO-TP transports and consumerless dependencies.
- Reduce CAN protocol code to vehicle frame types and decoders still used by the coordinator.
- Delete custom IDs, project-device simulation commands, API routes, topology and lifecycle
  projections.
- Delete `ApplicationEffect`, `EffectRequest`, `EffectExecutor`, effect failure inputs and
  `Commit.effects` now that no accepted effect remains.
- Keep low-level CAN endpoint send operations used by vehicle simulation, but remove configured live
  transmit authority and unused rate-policy machinery.
- Update current documentation and ADR status notes without rewriting historical decision bodies.

### Non-goals

- The independent Servotronic document, local device algorithm, status API or simulated HTTPS client.
- Changing the manual level representation or the Slice 06 `0..1` fixed-output conversion.
- Keeping an empty shared registry, generated protocol, transport, role type or effect stack for a
  later workstream to delete.

### Initial ownership

- steering portions of the controller domain, state, intents, kernel and snapshots
- Servotronic portions of output, protocol, health and diagnostics
- `hosts/src/e87canbus/protocol/servotronic_protocol.py`
- Servotronic simulation peer, controls and projections
- Servotronic frontend availability, activation and applied-output consumers
- `devices/servotronic-controller/`
- custom protocol sources, generator, CI and documentation
- generated protocol, registry, device catalogue, ISO-TP packages and embedded library
- configuration, deployment and composition device-source and TX fields
- output adapter and effect/failure portions of kernel, runners and diagnostics
- project-device simulation API, commands and topology
- focused affected tests and documentation

Integration exception: make the minimum commit and runtime signature changes required to remove
effects. Workstream 4 owns the broader surviving-contract audit.

### Required seams

- Desired state is never labelled applied or observed.
- Automatic mode selects desired automatic operation but does not evaluate the curve from
  coordinator speed.
- Fixed/manual and maximum choices remain accepted without device presence.
- Curve activation means selecting coordinator-owned desired configuration. It has no device
  acknowledgement state.
- Network reader and inbox faults remain health facts but no longer synthesize steering output.
- Vehicle `CanFrame`, network identity and decoding remain independent of deleted generated protocol
  code.
- Simulation can still inject vehicle frames through the production decoder.
- SocketCAN and in-memory endpoints may implement `send`, but live application composition creates
  no transmitter and exposes no command that can call it.
- Kernel commits describe accepted state and changed projections only.
- No compatibility module, no-op executor, legacy role type or empty protocol package remains.

### Acceptance criteria

- Desired modes, levels, maximum override and active curve operations still work.
- Vehicle speed remains visible but cannot generate a steering command.
- No Servotronic wire codec, effect, fallback, activation status, observed output, firmware or
  simulated peer remains.
- Steering actions and curve selection do not depend on registry state or adapter availability.
- Browser state contains desired steering values only.
- Button profile presentation remains valid without an unavailable Servotronic visual state.
- Repository searches find no custom protocol source or output, registry, heartbeat,
  acknowledgement, ISO-TP, `DeviceRole`, `DeviceSource`, project-device simulator control or old
  firmware.
- The generic effect and effect-failure architecture is absent.
- Runtime and simulator composition start without a device catalogue, registry or peer graph.
- Vehicle decoding and simulation still cross the real frame decoder.
- Live composition has no configured CAN transmit grant or rate policy.
- Dead dependencies, tests, fixtures, exports and current documentation are removed.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_architecture.py hosts/tests/test_config.py hosts/tests/test_application_controller.py hosts/tests/test_controller_loop.py hosts/tests/test_operator_intents.py hosts/tests/test_profile_api.py hosts/tests/test_runtime.py hosts/tests/test_live.py hosts/tests/test_simulation_bus.py hosts/tests/test_simulation_runtime.py hosts/tests/test_simulator_api.py hosts/tests/test_steering_curve_interpolation.py
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run affected frontend steering, profile and live tests plus application type checks. Run repository
searches for every deleted filename and symbol, and run the dependency lock check after removing
dependencies. A deleted test file is not a failed check when it covered only removed behavior;
record the deletion and run the surviving tests for each retained behavior named above.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 3 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/03-retire-servotronic-control.md, accepted dependency handoffs, Slice 1.5, ADR 0018 and Slice 06. Inspect the complete repository around steering state, reducer, kernel, output, protocol, registry, transport, simulator, persistence, live contract and frontend. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check the coordinator retains desired steering semantics, curves, vehicle frames and production-path vehicle simulation while removing every Servotronic calculation, command, fallback, acknowledgement, observation and availability rule. Check complete deletion of the custom protocol, registry, ISO-TP, DeviceRole, DeviceSource, old firmware, project-device simulation, effect execution, output failures and live CAN transmit configuration. Reject no-op shells, aliases, compatibility facades and future-action abstractions." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 3 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking desired-state, incomplete-deletion, dependency, commit-contract or vehicle-CAN regressions. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (review command used, or the subagent fallback that replaced it)
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
