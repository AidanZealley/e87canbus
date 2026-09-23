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
- Retain `ButtonPressed` and the kernel's press-to-intent dispatch, deleting only its CAN producer
  and the registry eligibility gate in front of it. Applying button intents to desired state is
  retained responsibility 2, so the input type keeps an approved consumer. It deliberately has no
  producer until Slice 02 adds the HTTP route; do not delete it as an orphan.
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
Servotronic until Workstream 3. Do not preserve any button-pad definition within them.

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

Run affected frontend live and profile tests plus application type checks. A deleted test file is
not a failed check when it covered only removed behavior. Record that deletion and run the surviving
tests for profile authoring, desired command behavior, Servotronic and vehicle CAN.

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 2 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/02-retire-button-pad-can.md, the accepted Workstream 1 handoff, Slice 1.5, ADR 0018 and linked documents. Inspect the uncommitted diff and surrounding profiles, kernel, output adapter, generated protocol, simulator, firmware and browser live consumers. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check complete removal of button-pad CAN and coordinator feedback while preserving profile authoring, active-state semantics and desired command behavior. Check no fake input, compatibility path or speculative vehicle action was added and Servotronic and vehicle CAN still work.
```

Closure review:

```text
Perform the focused closure review for Workstream 2 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking profile, state, deletion or regression defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `da5b3ca8db9cd4b875f5013e8dc81f936a1bafc6`
- Outcome: Removed button-pad CAN ingress, program and blink output, feedback state, the simulated NeoTrellis peer, AVR firmware and its consumerless embedded library. Profile authoring and selection, active profile identity, command active-state rules and direct `ButtonPressed` dispatch remain.
- Files changed: Button domain, controller and kernel; output adapter, protocol and generator; live models and generated browser client; simulated and live runtimes; old firmware and embedded library; affected backend and frontend tests; root, host, project context, setup, simulation, protocol and wiring documentation.
- Decisions: A press with no assignment or a saved command rejected by the current steering configuration produces no commit or feedback. `ButtonPressed` has no CAN or simulator producer until Slice 02 adds its HTTP route. Servotronic effects and the shared device-CAN infrastructure remain for Workstream 3.
- Verification: Targeted surviving backend tests passed (116); `generate_custom_protocol.py --check`, mypy, ruff, lint-imports and `git diff --check` passed. Frontend coordinator profile tests passed (25), console profile tests passed (26), coordinator-client live tests passed (11), all three affected package typechecks passed, and `pnpm api:check` passed. A focused search found no current-facing claim that the pad firmware, CAN transport or simulator peer still exists. Deleted LED presentation, button-pad vector, firmware-host and embedded C++ tests covered only retired behavior.
- Known limitations or external checks: No button-pad input exists in this intermediate workstream. No external validation gate applies.
- Specification drift: None.

## Independent review

- Reviewer: Fresh GPT-6 Sol agent.
- Verdict: Changes requested.
- Required findings: Current documentation still presents the retired button-pad CAN path as available. `README.md:123-128` instructs readers to build `devices/button-pad`, which this change deletes, and `README.md:150-153` says its firmware transmits on `0x700`. `PROJECT_CONTEXT.md:223-225,277-297` lists the deleted PlatformIO project and describes `0x700` button events, `0x701` feedback, ISO-TP programs and a firmware header as current. `hosts/README.md:42-52` still calls the button pad physical or emulated in every deployment. Update these current-facing descriptions to match the temporary absence of button input and pad firmware. Historical ADRs can remain historical.
- Optional observations: None.
- Questions: None.

Review evidence: The focused profile, CAN and registry suite passed (54 tests). The custom-protocol generator check and `git diff --check` passed. A search of the current protocol, device registry, simulator, output adapter and generated Servotronic header found no retained button-pad transport identifiers or peer code. Direct `ButtonPressed` dispatch and profile identity remain in the kernel, and the live buttons model no longer exposes program bytes.

## Resolution

- Finding dispositions: Accepted the one Required documentation finding. Updated `README.md`, `PROJECT_CONTEXT.md` and `hosts/README.md` to describe the absent pad and removed firmware while retaining accurate Servotronic and vehicle guidance.
- Simplification/deletion pass: Removed current build, upload, protocol and deployment instructions for the deleted button-pad path. The implementation removed its transport, output, feedback, firmware, simulator peer and consumerless library without a compatibility path.
- Final verification: The implementation's targeted backend and frontend checks passed. Remediation searched current-facing documentation for retired pad claims and passed `git diff --check`.

## Closure review

- Verdict: Approved. The accepted documentation finding is resolved.
- Remaining required findings: None. `README.md`, `PROJECT_CONTEXT.md` and `hosts/README.md` no longer direct readers to the deleted firmware or describe button-pad CAN as available. The cumulative diff retains profile identity and direct press-to-intent dispatch while removing pad program and feedback state. The focused profile, controller, runtime and live suite passed (73 tests), and `git diff --check` passed.
