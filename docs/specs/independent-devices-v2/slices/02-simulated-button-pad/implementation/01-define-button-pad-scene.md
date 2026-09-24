# Workstream 1: Define the independent button-pad scene

Status: not started.

## Task packet

### Outcome

The coordinator has one strict, transport-independent projection of the complete scene a button pad
must render. It preserves the useful profile behavior without restoring the deleted CAN protocol or
transient press-feedback state.

### Scope

- Define the button-pad configuration models used by persistence, HTTP and simulation later in this
  workflow.
- Port the colour and animation resolution named below rather than reinventing it.
- Project the active button profile and coordinator state into exactly 16 resolved button entries.
- Include global brightness `255` in this first delivery.
- Resolve each button's current colour from its configured inactive and active colours.
- Include an animation only while that button's configured action is active. An inactive button has
  no animation, even when its profile entry defines one.
- Exclude the deleted coordinator press-feedback overlay and every transport-specific field.
- Add focused tests for the projection and strict validation of the complete scene.

### Non-goals

- Authentication, persistence, generations, HTTP routes, SSE or simulation.
- Restoring button-pad CAN frames, device acknowledgements or a device registry.
- A generic scene renderer, arbitrary button counts, partial updates or per-device UI assignment.
- Button-pad transmission to vehicle CAN.

### Initial ownership

- the button profile and scene projection under `hosts/src/e87canbus/domain/buttons/`
- the button-pad configuration models under `hosts/src/e87canbus/api/`
- focused domain and model tests

Integration exception: make the smallest direct adjustment to the coordinator snapshot assembly if
that is the natural home for the projection. Do not open routes or introduce storage.

### Source to port

Slice 1.5 deletes `hosts/src/e87canbus/domain/controller/button_leds.py`, because its output type
`SetButtonPadProgram` and its browser `button_pad_program` consumer both go with the old device
platform. Its colour resolution is the most mature behavior in this area and is what this
workstream needs. Read it at the Slice 1.5 starting commit recorded in that workflow's plan and port
the state derivation and track rendering.

Preserve these decisions exactly:

- Three report states derive from the profile, never from the button index: an empty slot is
  unassigned, an assigned slot whose command condition holds is active, and any other assigned slot
  is inactive. Slice 1.5 removes the fourth `UNAVAILABLE` state with Servotronic availability
  gating; do not port it.
- An unassigned button renders solid off.
- An inactive button renders its authored colour scaled to a resting brightness of 8/255, rounded
  to the nearest byte rather than truncated. Truncation moves amber a step darker than the pad has
  ever shown, because 191 green scales to 5.99.
- An inactive button is static even when its slot authors an animation.
- An active button renders at full authored brightness. `active_colour` is reserved and always
  `None`, meaning the slot's `colour` at full brightness.
- A blink animation resolves back to the resting colour; a breathe animation resolves back to its
  own colour.

Do not port the `ButtonLedPresenter` protocol or the `ButtonLedProjection` dataclass. Both are
seams for a replaceable presenter that has one implementation. Port the functions directly.

Do not port the press-feedback blink overlay. It is coordinator-owned feedback that Slice 1.5
removes and this slice excludes.

### Required seams

- One validated scene model is shared by the later repository and API boundary; do not duplicate a
  persistence DTO and transport DTO.
- The projection consumes retained domain state and profile data only. It does not inspect a
  transport, subscriber or device connection.
- Animation is an optional property of each resolved button entry, absent unless its action is
  currently active.
- The model rejects missing, duplicate or extra button positions rather than silently repairing
  them.

### Acceptance criteria

- A valid profile projects to exactly 16 ordered button entries and global brightness `255`.
- Active and inactive colours resolve correctly from current coordinator state, including the
  ported resting brightness and its nearest-byte rounding.
- A configured animation appears only while its action is active.
- The model contains no press-feedback, CAN, registry, connection or applied-generation field.
- Invalid incomplete or oversized scenes fail validation at the model boundary.
- Targeted tests, type checking, linting and import-boundary checks pass.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_button_pad_scene.py hosts/tests/test_button_profile_runtime.py hosts/tests/test_button_profile_api.py
uv run mypy
uv run ruff check hosts
uv run lint-imports
git diff --check
```

The implementation agent creates `hosts/tests/test_button_pad_scene.py`.

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 1 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/01-define-button-pad-scene.md, the accepted Slice 1.5 handoff, linked source documents and relevant accepted ADRs. Inspect the uncommitted diff and surrounding button profile, coordinator snapshot and API model code. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check the exact 16-button complete scene, brightness 255, resolved active and inactive colours, active-only animation, strict model validation, absence of press feedback and transport fields, dependency direction and removal of obsolete alternatives. Reject a generic scene framework, partial-update protocol or restored device CAN compatibility.
```

Closure review:

```text
Perform the focused closure review for Workstream 1 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/01-define-button-pad-scene.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking scene semantics, validation or dependency defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `64183cd0c68a3d2fa7a94ae978873495d6926270`
- Outcome: Added a pure profile and state projection and one strict, complete button-pad scene model. It emits 16 ordered entries at brightness 255. Empty slots are off; assigned slots use full authored colour and their animation only while active, then a static colour rounded to the 8/255 resting level while inactive.
- Files changed: `hosts/src/e87canbus/domain/buttons/scene.py`, `hosts/src/e87canbus/api/models/button_pad.py`, `hosts/tests/test_button_pad_scene.py`, and this handoff.
- Decisions: The scene's array order is the physical button position, as in the approved JSON contract, so the fixed length rejects missing or extra positions and there is no separate position field to duplicate. The API model is the sole validated document for later storage and HTTP use. Domain resolution stays free of transport and persistence. Blink and breathe carry only the approved animation fields; the device renderer derives blink's resting colour from the resolved colour and breathe returns to its own colour.
- Verification: The targeted pytest suite passed (43 tests). `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports`, and `git diff --check` passed. The deletion pass found no obsolete scene code or duplicate persistence and transport models to remove.
- Known limitations or external checks: No external validation gate applies. Routes, storage and simulation belong to later workstreams.
- Specification drift: None.

## Independent review

- Reviewer: Fresh independent review agent.
- Verdict: Approved. The projection and validated document meet Workstream 1's scene contract.
- Required findings: None. `resolve_button_pad` walks the validated 16-slot profile in physical order, renders empty slots off, scales inactive authored colours by 8/255 with nearest-byte rounding, and includes the authored animation only for an active command. `ButtonPadScene.from_profile` sets brightness to 255. Its strict model requires exactly 16 entries and rejects missing fields, extra fields, wrong versions, invalid channel and animation bounds, and malformed animation types. The scene carries no coordinator press feedback, CAN transport, registry, connection or applied-generation field. The domain projection imports only retained domain state and profile rules; the API model adapts its result without reversing that dependency.
- Optional observations: None.
- Questions: None.

Review evidence: Compared the new projection with `button_leds.py` at the Slice 1.5 Workstream 2 base and checked the accepted Slice 1.5 handoff and superseding ADR 0018. The old presenter, CAN program and feedback overlay remain absent. The focused test command passed (43 tests); `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports` and `git diff --check` passed. The change adds no generic renderer, partial-update protocol or device-CAN compatibility path.

## Resolution

- Finding dispositions: No Required, Optional or Question findings. No remediation pass needed.
- Simplification/deletion pass: Confirmed the change adds one domain projection and one validated document, without a second DTO, presenter protocol, CAN compatibility path or coordinator feedback state.
- Final verification: Implementation, independent review and closure review passed the targeted 43 tests, mypy, Ruff, import boundaries and `git diff --check`.

## Closure review

- Verdict: Approved. The independent review accepted no Required findings, so there is no remediation to close. The cumulative diff has no release-blocking scene semantics, validation or dependency defect.
- Remaining required findings: None. The 16-slot profile yields 16 ordered buttons at brightness 255. Inactive colours use nearest-byte 8/255 scaling, and only active slots retain their authored animation. The strict document rejects incomplete and oversized button arrays, malformed entries and extra fields. Its `animation: null` representation matches the approved JSON contract for an inactive or unassigned button. The domain projection depends only on retained profile and application state; the API model performs the outward conversion.
- Closure evidence: The targeted tests passed (43 tests). `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports` and `git diff --check` passed on the cumulative worktree.
