# Workstream 3: Retire coordinator-side Servotronic control

Status: not started.

## Task packet

### Outcome

The coordinator owns desired steering state and curves but no longer calculates, sends, observes or
simulates Servotronic output.

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

### Non-goals

- The independent Servotronic document, local device algorithm, status API or simulated HTTPS client.
- Changing the manual level representation or the Slice 06 `0..1` fixed-output conversion.
- Deleting the shared registry or generated protocol before Workstream 4.

### Initial ownership

- steering portions of the controller domain, state, intents, kernel and snapshots
- Servotronic portions of output, protocol, health and diagnostics
- `hosts/src/e87canbus/protocol/servotronic_protocol.py`
- Servotronic simulation peer, controls and projections
- Servotronic frontend availability, activation and applied-output consumers
- `devices/servotronic-controller/`
- focused affected tests and documentation

Integration exception: make the minimum shared generated-protocol and registry edits needed to
remove Servotronic definitions while leaving the mechanism for Workstream 4 to delete.

### Required seams

- Desired state is never labelled applied or observed.
- Automatic mode selects desired automatic operation but does not evaluate the curve from
  coordinator speed.
- Fixed/manual and maximum choices remain accepted without device presence.
- Curve activation means selecting coordinator-owned desired configuration. It has no device
  acknowledgement state.
- Network reader and inbox faults remain health facts but no longer synthesize steering output.

### Acceptance criteria

- Desired modes, levels, maximum override and active curve operations still work.
- Vehicle speed remains visible but cannot generate a steering command.
- No Servotronic wire codec, effect, fallback, activation status, observed output, firmware or
  simulated peer remains.
- Steering actions and curve selection do not depend on registry state or adapter availability.
- Browser state contains desired steering values only.
- Button profile presentation remains valid without an unavailable Servotronic visual state.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_application_controller.py hosts/tests/test_controller_loop.py hosts/tests/test_operator_intents.py hosts/tests/test_profile_api.py hosts/tests/test_runtime.py hosts/tests/test_runtime_activation.py hosts/tests/test_live.py hosts/tests/test_simulation_runtime.py hosts/tests/test_simulator_api.py hosts/tests/test_steering_curve_interpolation.py
uv run python scripts/generate_custom_protocol.py --check
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_custom_protocol.py scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run affected frontend steering, profile and live tests plus application type checks.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 3 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/03-retire-servotronic-control.md, accepted dependency handoffs, Slice 1.5, ADR 0018 and Slice 06. Inspect the uncommitted diff and surrounding steering state, reducer, kernel, output, protocol, simulator, persistence, live contract and frontend. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check the coordinator retains desired steering semantics and curves while removing every calculation, command, fallback, acknowledgement, observation and availability rule tied to Servotronic execution. Confirm speed remains telemetry and no fake applied state or compatibility facade appears." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 3 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking desired-state, persistence, deletion or regression defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`
