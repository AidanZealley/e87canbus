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

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 3 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/03-retire-servotronic-control.md, accepted dependency handoffs, Slice 1.5, ADR 0018 and Slice 06. Inspect the complete repository around steering state, reducer, kernel, output, protocol, registry, transport, simulator, persistence, live contract and frontend. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check the coordinator retains desired steering semantics, curves, vehicle frames and production-path vehicle simulation while removing every Servotronic calculation, command, fallback, acknowledgement, observation and availability rule. Check complete deletion of the custom protocol, registry, ISO-TP, DeviceRole, DeviceSource, old firmware, project-device simulation, effect execution, output failures and live CAN transmit configuration. Reject no-op shells, aliases, compatibility facades and future-action abstractions.
```

Closure review:

```text
Perform the focused closure review for Workstream 3 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking desired-state, incomplete-deletion, dependency, commit-contract or vehicle-CAN regressions. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `16322347d93987916cba8c6cd441cffe4829aa36`
- Outcome: The coordinator retains desired steering modes, levels, maximum override and curve selection without calculating or sending Servotronic output. Vehicle speed remains telemetry. The Servotronic firmware, wire protocol, registry, ISO-TP transport, project-device simulator and generic effect stack are removed.
- Files changed: Steering domain/kernel and commit contracts; live and simulation composition; configuration, deployment, health and API models; console/coordinator UI and generated client; protocol sources and OpenAPI; firmware and transport directories; affected tests, dependencies, CI and current documentation.
- Decisions: The kernel accepts a vehicle-frame decoder for simulation; live composition has no decoder or transmitter. Simulation injects vehicle frames through the production decoder. The low-level CAN endpoint send operation remains for vehicle simulation. Removed tests that covered only deleted device behavior and kept focused tests for retained steering, vehicle and API behavior. After review, removed the unused steering-control availability props and inlined the curve chart rather than retaining a pass-through wrapper.
- Verification: `uv run pytest -q` passed (597 tests); final affected backend suite passed (153 tests). `uv run mypy`, `uv run ruff check hosts scripts/generate_openapi.py`, `uv run lint-imports`, `uv lock --check`, `pnpm api:check`, `pnpm typecheck`, `pnpm lint`, and `git diff --check` passed. Frontend Vitest passed with one worker: console (97), coordinator (36), coordinator-client (20). After review remediation, the three focused console suites passed (9 tests), and frontend typecheck, lint and diff check passed again. Repository searches confirmed removal of the deleted platform symbols and files from active code.
- Known limitations or external checks: Hardware CAN behavior was not exercised. The default parallel console Vitest run timed out on its route test; the full console suite passed with one worker.
- Specification drift: None.

## Independent review

- Reviewer: Independent Workstream 3 review agent.
- Verdict: Changes requested.
- Required findings:
  1. `docs/reliability.md:3-5,11-23,32-40` still describes device adapters, effect execution, steering and CAN-output fallbacks, emulator faults, device and steering health fields, and a safe output request on shutdown as current behavior. These paths were removed. Rewrite the current failure policy and health contract around the surviving CAN reader, inbox, persistence and publisher behavior.
  2. `deploy/systemd/controller.env.example:10-11` still says deployment profiles grant device sources and CAN transmission. The configuration and live composition no longer expose either choice. Update this installed configuration example so it does not advertise removed authority.
  3. `frontend/apps/console/src/components/steering-curve-editor/SteeringCurveEditor.tsx:36-49,145-163` and `components/curve-actions/CurveActions.tsx:25-43,51-101` retain `activationAvailable` and `modeControlAvailable` props that disable curve and desired steering controls. Repository search found no caller supplying either prop; both always default to true. Remove these dormant availability gates and their pass-through props instead of leaving a way to reinstate the retired device predicate.
- Optional observations: None.
- Questions: None.

Review evidence: The focused steering, profile, live, runtime, simulation and configuration suites passed (135 tests). OpenAPI generation `--check`, `uv lock --check` and `git diff --check` passed. Active-code searches found no Servotronic codec, device registry, ISO-TP transport, effect executor, output failure input, old firmware or live transmit grant. Desired steering state, curve persistence and selection, and simulation vehicle frames through the kernel decoder remain present. Hardware CAN was not exercised.

## Resolution

- Finding dispositions: Accepted all three Required findings. The current reliability guide and installed environment example describe deleted runtime behavior; the two frontend availability props leave dormant device gating in the desired-state controls. No Optional findings or Questions need disposition.
- Simplification/deletion pass: Updated the reliability guide and installed environment example to describe the surviving runtime. Removed unused frontend availability props and control gates, the now pass-through chart wrapper and its unused point-change callback. The original implementation deleted the Servotronic and shared device-CAN systems with their dead tests, dependencies and current documentation; it added no compatibility shell.
- Final verification: After remediation, focused console tests passed (9), as did frontend typecheck, lint and `git diff --check`. The implementation handoff records the full targeted checks. A search found none of the retired frontend gates or stale guide phrases.

## Closure review

- Verdict: Approved. All three accepted Required findings are resolved in the current cumulative diff.
- Remaining required findings: None. `docs/reliability.md` now describes reader, inbox, persistence and publisher behavior without steering-output fallbacks; `deploy/systemd/controller.env.example` no longer advertises device sources or TX grants; and the console curve editor and actions have no availability props or gates. The deleted chart wrapper and applied-output marker leave no replacement device predicate. The commit contract has no effects, the ISO-TP dependency is absent from the project and lockfile, and simulated vehicle frames still pass through the in-memory bus and kernel decoder. Focused backend tests passed (40), as did `uv lock --check` and `git diff --check`. Hardware CAN was not exercised.
