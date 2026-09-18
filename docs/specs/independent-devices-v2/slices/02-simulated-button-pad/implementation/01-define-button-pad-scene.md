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
- Active and inactive colours resolve correctly from current coordinator state.
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

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 1 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/01-define-button-pad-scene.md, the accepted Slice 1.5 handoff, linked source documents and relevant accepted ADRs. Inspect the uncommitted diff and surrounding button profile, coordinator snapshot and API model code. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check the exact 16-button complete scene, brightness 255, resolved active and inactive colours, active-only animation, strict model validation, absence of press feedback and transport fields, dependency direction and removal of obsolete alternatives. Reject a generic scene framework, partial-update protocol or restored device CAN compatibility." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 1 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/01-define-button-pad-scene.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking scene semantics, validation or dependency defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
