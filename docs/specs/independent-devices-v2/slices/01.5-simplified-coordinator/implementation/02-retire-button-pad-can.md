# Workstream 2: Retire button-pad CAN and coordinator feedback

Status: not started.

## Task packet

### Outcome

The coordinator retains button profiles and desired active state but has no button-pad transport,
rendered byte program, press ingress or coordinator-owned acknowledgement feedback.

### Scope

- Delete button-pad CAN event decoding, registry eligibility, ISO-TP program output, incremental
  blink output, generated definitions and byte-vector conversions.
- Delete `ButtonPadProgram`, coordinator feedback state, feedback deadlines, failure and
  acknowledgement blinks, and effect-origin button correlation where button output was its consumer.
- Preserve profile assignment, authored colours and animations, command active-state evaluation and
  active profile identity. Do not create the Slice 02 JSON scene yet.
- Remove raw button programs and feedback from browser live models and consumers.
- Delete the old AVR firmware, its protocol headers, the NeoTrellis CAN peer and button-specific
  simulator controls.
- Delete `embedded-libs/button_pad_effects` if repository search confirms no remaining consumer.
- Remove or rewrite tests and documentation that assert the retired path.

### Non-goals

- Independent device models, authentication, HTTP presses, configuration persistence or SSE.
- Servotronic or shared registry deletion while those consumers remain.
- A dormant transport switch, compatibility input or direct vehicle-CAN action.

### Initial ownership

- button-specific code in `hosts/src/e87canbus/domain/buttons/`, controller domain and kernel
- button-specific code in the output adapter, protocol router and generated custom protocol
- button-pad live models and frontend consumers
- `hosts/src/e87canbus/runners/simulation/devices/neotrellis.py` and related controls
- `devices/button-pad/` and consumerless embedded button-pad libraries
- affected backend and frontend tests and documentation

Integration exception: keep the shared generated protocol, registry and ISO-TP files compiling for
Servotronic until Workstream 4. Do not preserve any button-pad definition within them.

### Required seams

- Button profile commands still change desired application state through direct operator-intent
  tests even though no physical or simulated pad can originate a press yet.
- Active-state evaluation remains semantic. It does not render or encode a device program.
- No coordinator state records transient local press feedback.
- The temporary lack of button input is explicit and does not produce a fake simulator path.

### Acceptance criteria

- No button-pad CAN identifier, codec, ISO-TP payload, registry branch, firmware or simulated peer
  remains.
- No coordinator feedback state, deadline, blink effect or origin-correlation behavior remains.
- Browser contracts contain no raw button program or feedback overlay.
- Profile CRUD, active profile selection, authored presentation and command active-state rules still
  work.
- Servotronic and vehicle CAN behavior remain unchanged for their later owners.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_button_led_presentation.py hosts/tests/test_button_profile_runtime.py hosts/tests/test_button_profile_api.py hosts/tests/test_application_controller.py hosts/tests/test_runtime.py hosts/tests/test_simulation_runtime.py hosts/tests/test_simulator_api.py hosts/tests/test_live.py hosts/tests/test_generated_protocol.py
uv run python scripts/generate_custom_protocol.py --check
uv run mypy
uv run ruff check hosts scripts/generate_custom_protocol.py
uv run lint-imports
git diff --check
```

Run affected frontend live and profile tests plus application type checks.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 2 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/02-retire-button-pad-can.md, the accepted Workstream 1 handoff, Slice 1.5, ADR 0018 and linked documents. Inspect the uncommitted diff and surrounding profiles, kernel, output adapter, generated protocol, simulator, firmware and browser live consumers. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check complete removal of button-pad CAN and coordinator feedback while preserving profile authoring, active-state semantics and desired command behavior. Check no fake input, compatibility path or speculative vehicle action was added and Servotronic and vehicle CAN still work." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 2 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking profile, state, deletion or regression defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
