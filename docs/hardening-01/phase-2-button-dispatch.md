# Phase 2 — Button dispatch table in the application controller

## Goal

Replace the growing if-chain in `ApplicationController.handle_event`
(`coordinator/src/e87canbus/application/controller.py:62-114`) with a lookup table of small,
named handler methods — one per button — so that adding the next feature adds a table entry and a
handler, not another branch. **Strictly behaviour-preserving:** every existing test in
`tests/test_application_controller.py`, `tests/test_runtime.py`, `tests/test_simulation_controller.py`,
and `tests/test_simulator_api.py` must pass unchanged.

## Why

`handle_event` is already ~50 lines of nested conditionals for four buttons, with the
maximum-assistance guard woven across branches. DSC, strobe, and MFL features will each add
buttons; on the current shape that produces the god function the hardening pass exists to
prevent. A dict of `button_index -> handler` keeps each button's complete behaviour readable in
one place.

## Current behaviour (must be preserved exactly)

Read the existing tests first — they are the specification. In summary:

- `SpeedUpdateEvent` → `state.set_speed`, no outputs.
- Button releases → no outputs, no state change.
- Button 3 (maximum assistance) toggles: on activate, saves `(steering_mode,
  manual_assistance_level)`, forces `MANUAL` at max level, sets the flag; on deactivate, restores
  the saved pair and clears the flag. Both directions return the mode LED and the max LED.
- Buttons 1/2 (assistance down/up) **while max assistance is active**: restore the saved state,
  force `MANUAL`, return both LEDs, and do **not** nudge the level on that press.
- Button 0 (mode) **while max assistance is active**: no-op returning `()` — it must not mutate
  the state that button 3 will restore.
- Button 0 otherwise: toggles AUTO ↔ MANUAL, returns the mode LED.
- Buttons 1/2 otherwise: first press from AUTO switches to MANUAL (no nudge) and returns the mode
  LED; in MANUAL, nudges the level by ∓1 clamped to `[0, manual_level_count - 1]`, returns `()`.
- Unknown button indices: no-op, `()`.

## Design (decided — implement as written)

- `handle_event` becomes a short entry point: handle `SpeedUpdateEvent`, ignore releases, then
  `handler = self._button_handlers.get(event.button_index)` and call it (unknown index → `()`).
  Target ≤ 15 lines.
- `self._button_handlers: dict[int, Callable[[], tuple[ApplicationOutput, ...]]]` built once in
  `__init__` from the existing class constants:

  ```
  STEERING_MODE_BUTTON_INDEX          -> self._handle_steering_mode_button
  MANUAL_ASSISTANCE_DOWN_BUTTON_INDEX -> self._handle_assistance_down_button
  MANUAL_ASSISTANCE_UP_BUTTON_INDEX   -> self._handle_assistance_up_button
  MAXIMUM_ASSISTANCE_BUTTON_INDEX     -> self._toggle_maximum_assistance   (already exists)
  ```

- Each handler is self-contained: it checks `maximum_assistance_active` itself at the top and
  handles its own guard behaviour. This trades one line of duplication between the down/up
  handlers for the property that a reader sees a button's entire behaviour in one method — that
  trade is the point of this phase.
- The down/up handlers share their common logic through one private helper
  (`_nudge_manual_assistance(delta: int)` or similar); the two public-facing handlers stay
  trivial wrappers so the dispatch table remains plain method references — **no lambdas or
  `functools.partial` in the table.**
- The class constants remain the single source of truth for button indices (the duplicate
  `NEOTRELLIS_BUTTON_NOTES` table was deleted in phase 1).
- No registries, no decorator-based registration, no base classes. A dict and four methods.

## Tasks

1. Refactor as designed. Do not change `desired_outputs`, the LED helper methods, or any
   signatures used by `runtime.py`.
2. Run the full test suite — zero test edits allowed. If a test fails, your refactor changed
   behaviour; fix the refactor, not the test.
3. Add one new test: unknown button index (e.g. 9) pressed → `()` returned and a snapshot taken
   before/after compares equal. (This behaviour existed implicitly; it becomes explicit contract.)

## Out of scope

- New outputs, steering current computation, or any time-based behaviour (phase 3).
- Changes to `events.py`, `state.py`, `router.py`, or the simulator.

## Acceptance criteria

- `handle_event` contains no `if event.button_index ==` chains; dispatch is via the dict.
- All pre-existing tests pass **unmodified**; the one new test passes.
- `uv run pytest -q`, `uv run mypy`, `uv run ruff check coordinator` all pass.
