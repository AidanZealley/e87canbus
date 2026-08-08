# Workstream 1: shared panel and hotspot services

Status: not started.

## Task packet

### Outcome

Implement the small, platform-independent Python behaviour used unchanged by production and the
simulator. At completion, focused tests can drive coordinator status, hotspot observations, and
button presses without FastAPI, UART, NetworkManager, threads, or frontend code.

### Scope

- Add a typed `panel` module containing coordinator status, the six semantic display values,
  display derivation, button readiness gating, and the direct output seam required by two real
  environments.
- Add a typed `hotspot` module containing hotspot state, toggle decisions, command-failure
  behaviour, and the small backend seam described by the specification.
- Ensure a physical or simulated button enters through the same panel-service method.
- Add focused unit tests for meaningful transitions and display priority.
- Export only the symbols actual consumers need.

Prefer a small number of direct modules such as `e87canbus.panel` and `e87canbus.hotspot`. Do not
create packages full of one-class files unless the implementation has a demonstrated readability
need.

### Non-goals

- Kernel, `ControllerLoop`, API, runner, serial, NetworkManager, threading, or frontend changes.
- A generic local-controls framework, command bus, event stream, repository, or lifecycle base.
- Retries, persistence, dynamic configuration, or speculative error states.
- Exhaustive transition permutations.

### Initial ownership

- `coordinator/src/e87canbus/panel.py` or an equally small agreed module.
- `coordinator/src/e87canbus/hotspot.py` or an equally small agreed module.
- New focused tests for those modules under `coordinator/tests/`.
- This workstream record.

If existing architecture makes different exact paths materially better, record the choice before
using it. Do not touch integration files in this workstream.

### Required seams

- Input: the four-value `CoordinatorStatus` projection.
- Input: hotspot observation through `HotspotService`.
- Input: one button-pressed operation.
- Output: one `PanelDisplay` semantic value.
- Output: activate or deactivate through the narrow hotspot backend.

The service must be usable with both NetworkManager and in-memory backends without containing a
profile check.

### Acceptance criteria

- The exact display priority and button table in the specification are represented once.
- A press before coordinator readiness is ignored.
- A press while hotspot activation is starting requests disable/cancellation.
- Hotspot command failure becomes `failed`; another press retries activation.
- No shared service imports API, runners, adapters, kernel, or OS-specific libraries.
- Tests are focused on product rules rather than every enum combination.

### Targeted verification

```bash
uv run pytest coordinator/tests/test_panel.py coordinator/tests/test_hotspot.py
uv run ruff check coordinator/src/e87canbus/panel.py coordinator/src/e87canbus/hotspot.py \
  coordinator/tests/test_panel.py coordinator/tests/test_hotspot.py
uv run mypy coordinator/src/e87canbus
uv run lint-imports
```

Adjust filenames in the record if the accepted implementation uses different small paths.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations: `TBD`
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
