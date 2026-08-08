# Workstream 1: shared panel and hotspot services

Status: accepted.

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

- Base commit: `6179d6f8d23a1dc5b7c34d3fc5c739c053f255dc`
- Outcome: Added the shared typed hotspot state machine and panel display service, including the
  common button entry point, readiness gating, display priority, output seam, and focused tests.
- Files changed: `coordinator/src/e87canbus/hotspot.py`,
  `coordinator/src/e87canbus/panel.py`, `coordinator/tests/test_hotspot.py`,
  `coordinator/tests/test_panel.py`, and this record.
- Decisions: A command failure remains visible while the backend reports the observation from
  which the command failed; successful retry or observed state progress clears it. This preserves
  the required visible failure and retry button behaviour while allowing later backend evidence to
  recover it. Each toggle is a direct synchronous operation, so no thread or lifecycle machinery
  is needed in the shared service; application composition remains responsible only for scheduling
  refreshes.
- Verification: `uv run pytest coordinator/tests/test_panel.py coordinator/tests/test_hotspot.py`
  (8 passed); focused `uv run ruff check ...` (passed); `uv run mypy
  coordinator/src/e87canbus` (passed); `uv run lint-imports` (2 contracts kept).
- Known limitations: The services expose a direct `refresh()` operation; production and simulator
  composition must call it when observations can change independently of a button press. This is
  intentional under the workstream boundary.
- Specification drift: `None`.

## Independent review

- Reviewer: `Codex /root/ws1_review`
- Verdict: `Changes required`
- Required findings:
  - `HotspotService.toggle()` treats any latched command failure as the current `failed` state
    without reconciling the fresh backend observation it has just read. Reproduced by failing an
    activation from `disabled`, changing the backend observation to `connected`, and pressing the
    button before calling `status()`: the service issues `activate` again instead of `deactivate`.
    This violates the requirements that a successful later observation clears the failure and that
    the hotspot service owns the toggle decision rather than deciding from stale state; in a real
    late-completing activation it can leave an active hotspot enabled when the press should disable
    it. Use one shared observation-to-status reconciliation path from both `status()` and
    `toggle()`, so observation progress clears the latch before applying the transition table, and
    protect this path with a focused test.
- Optional observations: `None`.
- Questions for orchestrator: `None`.

## Resolution

- Finding dispositions: Accepted the required failure-latch reconciliation finding. A fresh
  backend observation must determine the button action when it demonstrates progress beyond the
  observation at which the prior command failed.
- Simplification/deletion pass: Replaced the duplicated, stale toggle-status calculation with one
  small observation reconciliation helper shared by `status()` and `toggle()`. Replaced the weaker
  status-only recovery test with the complete failure, observed progress, and button-action path;
  no compatibility machinery or obsolete code remains.
- Final verification: Final accepted-tree verification passed: `uv run pytest
  coordinator/tests/test_panel.py coordinator/tests/test_hotspot.py` (8 passed); focused `uv run
  ruff check ...` (passed); `uv run mypy coordinator/src/e87canbus` (passed); `uv run lint-imports`
  (2 contracts kept).

## Closure review

- Verdict: `Accepted`
- Remaining required findings: `None`. `status()` and `toggle()` now use the same fresh-observation
  reconciliation path. The focused test confirms that a failed activation followed by an observed
  `connected` state causes the next press to deactivate, and the targeted tests, Ruff, and mypy
  pass.
- Accepted commit: `a17dd72e874ed43f3280f46f9cf91e31717ee64c`
