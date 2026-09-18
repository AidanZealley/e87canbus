# Workstream 1: Remove the high-beam flash feature

Status: not started.

## Task packet

### Outcome

The simulator-only high-beam flash command, state and UI are gone. Stored button profiles preserve
their other bindings and turn every retired high-beam slot into an unassigned slot.

### Scope

- Remove `start_high_beam_strobe` from domain intents, the button command catalogue, built-in
  profiles, request/response models, generated catalogue and both profile editors.
- Add the ordered SQLite migration that rewrites only affected stored slots to unassigned and
  advances profile revision according to the repository's existing rules.
- Remove high-beam timing configuration, application state, transition logic, deadlines, effects,
  simulated actuator and private simulation frame.
- Remove the lighting state topic, live projection, dashboard display and simulator control that
  exist only for this feature.
- Regenerate OpenAPI, Hey API and button-command catalogue artifacts from their sources.
- Delete tests and fixtures that only prove the retired behavior. Retain tests that protect profile
  migration and unrelated commands.

### Non-goals

- A replacement headlight command, vehicle CAN ID, firmware behavior or generic action hook.
- Button-pad CAN removal, Servotronic cleanup or the shared effect executor while it has consumers.
- Changes to button colour and animation authoring.

### Initial ownership

- high-beam portions of `hosts/src/e87canbus/config.py`, domain state, intents, reducer and snapshots
- button profile catalogue, persistence migration and API models
- simulation high-beam protocol, actuator and vehicle state
- coordinator and console frontend lighting/profile consumers
- generated OpenAPI, coordinator client and button-command catalogue artifacts
- focused backend and frontend tests and current documentation

Integration exception: update the controller deadline calculation and live model only as required to
remove this feature. Workstream 5 owns broader contract simplification.

### Required seams

- Migration rewrites the command structurally. It does not use a permanent deprecated parser at the
  current API boundary.
- A profile with several bindings loses only high-beam slots. Its remaining slot order, authored
  colour, animation and identity survive.
- The built-in profile leaves the old high-beam slot unassigned rather than replacing it with a new
  command.
- No generated file is hand-edited.

### Acceptance criteria

- No API or editor can create or return `start_high_beam_strobe`.
- A database containing that command upgrades with only those slots cleared and remains readable.
- High-beam state, effects, deadlines, simulation frames, live fields and UI are absent.
- Other button commands and profile CRUD still work.
- Repository searches find no retained high-beam flash implementation or compatibility spelling.

### Targeted verification

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
claude -p "Act as the independent reviewer for Workstream 1 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/01-remove-high-beam-flash.md, Slice 1.5, ADR 0018 and linked product documents. Inspect the uncommitted diff and surrounding profile migration, command catalogue, domain state, timers, simulation, live models, generated contracts and frontend consumers. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that the feature is completely removed, stored profiles lose only retired slots, no compatibility parser or future action hook remains, and unrelated profile behavior survives." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 1 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking migration, contract or incomplete-deletion defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
