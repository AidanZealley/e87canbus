# Phase 1 — Dead code deletion and boundary cleanup

## Goal

Shrink the codebase to only what is real and wired up, fix two layer-boundary leaks, and add a
cheap guard against firmware/protocol drift. Everything in this phase is either a deletion, a
move, or a small type tightening. No new behaviour except the drift-guard test.

## Why

The review found a features layer that is almost entirely orphaned (placeholder stubs, an unused
MFL mapping table that duplicates constants in `ApplicationController`, dead event types), a dead
`strobe_active` state field that is serialized all the way to the frontend but can never be set,
and a duplicate `SocketCanBus` stub in the protocol layer that is a wrong-import trap. Later
phases refactor the controller and add time/TX machinery; doing that on top of dead code multiplies
confusion. Git history preserves everything deleted here — features get rebuilt properly when
their phase (or their verified CAN captures) arrive.

## Verified current state

These usages were confirmed by grep on 2026-07-13. Re-verify with grep before deleting anything —
if a symbol has gained a caller since, stop and note it in the log.

- `SocketCanBus` stub at `coordinator/src/e87canbus/protocol/can.py:104` — **no importers**. The
  real adapter is `adapters/socketcan.py`.
- `PwmSteeringDriver` at `coordinator/src/e87canbus/features/steering.py:50` — **no importers, no
  tests**.
- `features/button_mapping.py`, `features/dsc.py`, `features/strobe.py` — imported only by their
  own tests (`tests/test_button_mapping.py`). `NEOTRELLIS_BUTTON_NOTES` duplicates the button
  index constants on `ApplicationController`.
- Unused event types in `application/events.py`: `MflButton`, `MflButtonEvent`, `DscCommand`,
  `DscCommandRequest`, `HighBeamStrobeRequest`, `SteeringModeChange`,
  `ManualAssistanceLevelChange`. Referenced only by `tests/test_events.py`,
  `tests/test_button_mapping.py`, and the files being deleted.
- `strobe_active`: set nowhere; read in `application/state.py:32`,
  `application/controller.py` (snapshot field), `simulation/controller.py` (`snapshot_to_dict`),
  `frontend/src/components/simulator-workbench/types.ts:29`, and
  `SimulatorWorkbench.tsx:35` (emptySnapshot). `SteeringStatus.tsx` does **not** render it.
- Compatibility aliases `self.network` / `self.pi_bus` at
  `coordinator/src/e87canbus/simulation/controller.py:195-196` — **no callers** outside their own
  definition (tests use `controller.pi_buses`).
- `SpeedUpdateEvent.source_bus` is a raw `str` (`application/events.py:63`); used in
  `tests/test_events.py:26` and `tests/test_application_controller.py:170`.
- `protocol/can.py` imports `ButtonLedCommand` and `LedColour` from `application.events` solely
  for `LED_COLOUR_CODES` and `encode_button_led_command` (`can.py:6, 19-26, 86-93`). The only
  caller of `encode_button_led_command` is `protocol/router.py`.
- Duplicate trace storage: `InMemoryCanNetwork._send` (`simulation/bus.py:79-98`) appends every
  entry to its own `_trace` deque even when a topology `recorder` is set — so topology-owned
  networks store every frame twice. Nothing reads the per-network trace of a topology-owned
  network (the only reader was the compat alias above).

## Tasks

Work in this order; run `uv run pytest -q` after each numbered task to keep failures local.

### 1. Delete the protocol-layer `SocketCanBus` stub

Remove the class at `protocol/can.py:104-109`. `adapters/socketcan.py` is unaffected.

### 2. Delete speculative feature placeholders

- Delete `coordinator/src/e87canbus/features/button_mapping.py`, `features/dsc.py`,
  `features/strobe.py`, and `coordinator/tests/test_button_mapping.py`.
- In `features/steering.py`, delete only `PwmSteeringDriver`. **Keep** `clamp_manual_level`,
  `interpolate_speed_to_current`, and `target_current_to_normalized_command` — they are the
  verified core math of the imminent steering feature and are covered by `tests/test_steering.py`.
- In `application/events.py`, delete the seven unused types listed above. Keep `SteeringMode`,
  `ButtonState`, `LedColour`, `NeoTrellisButtonEvent`, `ButtonLedCommand`, `SpeedUpdateEvent`.
- In `config.py`, delete `StrobeConfig` and its `AppConfig.strobe` field (it configured the
  deleted placeholder). **Keep** `PlaceholderBmwIds` — it is reference data documenting
  unverified IDs, which is exactly what it says it is. Keep `SteeringConfig`.
- Update `tests/test_events.py` and `tests/test_config.py` for the removals.
- Update `coordinator/README.md` (its features line names "steering, strobe, DSC, and button
  mapping") and grep `docs/` for any sentence this invalidates. `PROJECT_CONTEXT.md` describes
  *planned car features*, not code — leave it alone.

### 3. Delete dead `strobe_active` state end to end

Remove the field from `RuntimeState`, `ApplicationSnapshot`, the `snapshot()` methods, the
`snapshot_to_dict` serializer in `simulation/controller.py`, the frontend `ApplicationSnapshot`
type, and the `emptySnapshot` constant. Check `docs/simulation.md` for mentions. When the strobe
feature is actually built (post-hardening, against the phase 3 tick), it re-adds what it needs.

### 4. Tighten `SpeedUpdateEvent.source_bus`

Rename to `source_network: CanNetwork` (import `CanNetwork` from `e87canbus.config` — the
application layer already imports config; this preserves import direction). Update the two test
usages; `"simulated-vehicle"` in `test_application_controller.py:170` becomes `CanNetwork.FCAN`.

### 5. Make `protocol/can.py` purely wire-format

Move `LED_COLOUR_CODES` and `encode_button_led_command` from `can.py` into `router.py` (the
router is the app↔wire mapping layer; `_encode_button_led_command` there can inline the
conversion: look up the colour code, build a `LedUpdatePayload`, call `encode_led_update`).
After the move, `can.py` must import nothing from `e87canbus.application`. Move or fold any
tests in `tests/test_can_protocol.py` that covered the moved function into router coverage.

### 6. Remove duplicate trace storage and the compat aliases

- In `simulation/bus.py`: in `_send`, append to the network's own `_trace` **only when
  `self._recorder is None`** (standalone networks, as used by `simulation/bench.py` and the bus
  tests, keep their local trace; topology-owned networks record solely through the topology).
  Keep `trace()` / `clear_trace()` working for standalone use.
- Delete the two compat alias lines in `simulation/controller.py:194-196` and the comment above
  them.
- If any test asserted on a topology-owned network's local trace, point it at
  `topology.trace()` instead.

### 7. Add the firmware/protocol drift guard

New file `coordinator/tests/test_firmware_protocol_sync.py`: parse
`devices/button-pad/include/can_ids.h` with a small regex helper (one function:
`constants_from_header(text) -> dict[str, int]`, matching lines like
`static const <type> NAME = 0xNN;` — handle both hex and decimal) and assert:

- `CAN_ID_BUTTON_EVENT == CustomCanIds().button_event` and
  `CAN_ID_LED_UPDATE == CustomCanIds().led_update`
- `BUTTON_PRESSED` / `BUTTON_RELEASED` match `protocol.can.BUTTON_PRESSED` / `BUTTON_RELEASED`
- `LED_COLOUR_OFF..LED_COLOUR_WHITE` match `protocol.can.LED_OFF..LED_WHITE`

Locate the header relative to the test file
(`Path(__file__).resolve().parents[2] / "devices" / "button-pad" / "include" / "can_ids.h"`)
so it works from any CWD. Do not modify the header — the point is to fail CI when either side
drifts.

## Out of scope

- Any change to `ApplicationController.handle_event` logic (phase 2).
- Anything time-related (phase 3).
- The websocket/API payload shape (phase 5) — the frontend change here is limited to deleting
  the `strobe_active` field.

## Acceptance criteria

- `grep -rn "strobe\|Mfl\|DscCommand\|PwmSteeringDriver\|button_mapping" coordinator/src` returns
  nothing (config `PlaceholderBmwIds.possible_dsc_request_ids` and docs excepted).
- `protocol/can.py` has no `e87canbus.application` import.
- All checks pass: `uv run pytest -q`, `uv run mypy`, `uv run ruff check coordinator`, and
  `cd frontend && pnpm typecheck && pnpm lint`.
- The new drift-guard test fails if you temporarily change an ID in `can_ids.h` (verify once
  manually, then revert).
- Net line count of `coordinator/src` goes **down**.
