# Workstream 1: Remove the high-beam flash feature

Status: not started.

## Task packet

### Outcome

The simulator-only high-beam flash command, state and UI are gone. A fresh database contains one
selected empty `Default` button profile with no product-specific assignments.

### Scope

- Remove `start_high_beam_strobe` from domain intents, the button command catalogue,
  profiles, request/response models, generated catalogue and both profile editors.
- Do not migrate existing application databases. Record that prototype databases must be replaced.
- Seed one protected, selected profile named `Default` with exactly sixteen unassigned slots.
- Remove command-specific built-in assignments, reserved button indexes and configurable high-beam
  placement. Keep the non-empty catalogue and selected-profile invariants.
- Remove high-beam timing configuration, application state, transition logic, deadlines, effects,
  simulated actuator and private simulation frame.
- Remove the lighting state topic, live projection, dashboard display and simulator control that
  exist only for this feature.
- Regenerate OpenAPI, Hey API and button-command catalogue artifacts from their sources.
- Delete tests and fixtures that only prove the retired behavior. Retain tests that protect the
  empty seed, selection invariant and unrelated profile operations.

### Non-goals

- A replacement headlight command, vehicle CAN ID, firmware behavior or generic action hook.
- Button-pad CAN removal, Servotronic cleanup or the shared effect executor while it has consumers.
- Changes to button colour and animation authoring.

### Initial ownership

- high-beam portions of `hosts/src/e87canbus/config.py`, domain state, intents, reducer and snapshots
- button profile catalogue, fresh-database seed and API models
- simulation high-beam protocol, actuator and vehicle state
- coordinator and console frontend lighting/profile consumers
- generated OpenAPI, coordinator client and button-command catalogue artifacts
- focused backend and frontend tests and current documentation

Integration exception: update the controller deadline calculation and live model only as required to
remove this feature. Workstream 4 owns broader contract simplification.

### Required seams

- A fresh database has one selected `Default` profile containing sixteen unassigned slots.
- The seed does not name or instantiate any button command.
- Existing prototype databases have no compatibility parser or migration path.
- No generated file is hand-edited.

### Acceptance criteria

- No API or editor can create or return `start_high_beam_strobe`.
- A fresh database contains the selected empty `Default` profile and supports profile CRUD and
  selection without nullable-profile machinery.
- High-beam state, effects, deadlines, simulation frames, live fields and UI are absent.
- Other button commands and profile CRUD still work.
- Repository searches find no retained high-beam flash implementation or compatibility spelling.

### Targeted verification

Run these once on the starting commit before any implementation diff exists and record the
baseline in the plan's orchestration record, so pre-existing failures are not attributed to this
workstream.

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_sqlite_button_profiles.py hosts/tests/test_button_profile_api.py hosts/tests/test_operator_intents.py hosts/tests/test_runtime.py hosts/tests/test_simulation_runtime.py hosts/tests/test_live.py hosts/tests/test_openapi_contract.py
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm --filter @e87canbus/coordinator-client typecheck
pnpm --filter @e87canbus/coordinator test
pnpm --filter @e87canbus/console test
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 1 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/01-remove-high-beam-flash.md, Slice 1.5, ADR 0018 and linked product documents. Inspect the uncommitted diff and surrounding fresh-database seed, profile catalogue, domain state, timers, simulation, live models, generated contracts and frontend consumers. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that the feature and its command-specific defaults are completely removed, a fresh database has one selected empty Default profile, no migration, compatibility parser or future action hook remains, and unrelated profile behavior survives." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 1 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking seed, contract or incomplete-deletion defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
