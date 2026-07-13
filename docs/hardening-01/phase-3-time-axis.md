# Phase 3 — Time axis: tick, injectable clocks, speed-staleness failsafe

## Goal

Give the coordinator a concept of time. A purely frame-driven runtime can never fail safe,
because a silent bus produces no callbacks — and the project's most safety-critical behaviours
(speed-staleness failsafe for the steering solenoid, strobe sequencing, control-loop ticks) are
all time-driven. This phase adds a `tick` path through runtime and application, threads
injectable clocks everywhere time is read, and implements the first consumer: a speed-staleness
flag that the future steering feature will treat as "fall back to safe assistance current".

This is the foundation phase — later phases and every future feature build on it.

## Why this shape

- Frame handling and tick handling are the **only two entry points** into the application. Both
  return `tuple[ApplicationOutput, ...]` and both dispatch through the same
  `runtime._send_outputs`, so simulation and live keep sharing one path.
- Clocks are injected as `Callable[[], float]` (the pattern `CoordinatorRuntime` already uses at
  `runtime.py:25`), never read via `time.monotonic()` inside logic. This makes
  unsafe-to-road-test scenarios ("F-CAN dies at t=5s") deterministic unit tests.

## Design (decided — implement as written)

### Application layer

- `RuntimeState` (`application/state.py`) gains:
  - `speed_updated_monotonic_s: float | None = None`
  - `speed_valid: bool = False`
  - `set_speed(self, speed_kph: float, now: float)` — sets speed (existing clamp), records
    `now`, sets `speed_valid = True`.
- `SteeringConfig` (`config.py`) gains `speed_timeout_s: float = 1.0`. (Wheel speed broadcasts at
  tens of Hz on the real bus; 1 s of silence is unambiguously stale while staying friendly to
  the simulator.)
- `AppConfig` gains `tick_interval_s: float = 0.1` — one field, used by the simulator API loop in
  this phase and reused by the live runner in phase 6.
- `ApplicationController.handle_event` signature becomes
  `handle_event(self, event: ApplicationEvent, now: float)`. The `SpeedUpdateEvent` branch passes
  `now` to `set_speed`. (Button handlers ignore `now` for now — do not thread it into them.)
- New `ApplicationController.tick(self, now: float) -> tuple[ApplicationOutput, ...]`:
  recomputes `state.speed_valid` (`False` when never updated or when
  `now - speed_updated_monotonic_s > steering_config.speed_timeout_s`), returns `()` for now.
  Keep it a plain method that future features extend with real outputs; **do not** build a
  task-scheduler abstraction.
- `ApplicationSnapshot` gains `speed_valid: bool`.

### Runtime

- `CoordinatorRuntime.process_frame` passes `self._monotonic()` as `now` to `handle_event`
  (it already computes it for `can_health`; call the clock once and reuse the value).
- New `CoordinatorRuntime.tick(self) -> None`:
  `self._send_outputs(self.application.tick(self._monotonic()))`.

### Simulation

- `InMemoryCanNetwork` and `InMemoryCanTopology` (`simulation/bus.py`) gain a
  `clock: Callable[[], float] = time.monotonic` parameter used for trace timestamps; the
  topology passes its clock to the networks it creates.
- `SimulatorController` gains `clock: Callable[[], float] = time.monotonic`, passed to the
  topology and as `monotonic=` to the runtime.
- New `SimulatorController.tick(self) -> SimulatorSnapshot`: record `before_sequence`, call
  `self.runtime.tick()`, then return `self._process_pending(before_sequence)` so any outputs a
  tick produces flow through the buses and event stream exactly like button-driven outputs.

### API

- In `create_app` (`api/simulator.py`), add a background task (FastAPI lifespan, not
  `@app.on_event`) that loops: sleep `config.tick_interval_s`, then under `app.state.lock` call
  `controller.tick()`, and **broadcast only if the application snapshot changed** since the last
  tick (frozen dataclass equality — keep the previous snapshot in a local variable). This keeps
  the websocket quiet while idle. The controller needs access to its `AppConfig`
  (`SimulatorController` already stores `self.config`).
- Ensure clean shutdown: the lifespan cancels the task on exit. The existing module-level
  `app = create_app()` stays.

### Frontend

- Add `speed_valid: boolean` to `ApplicationSnapshot` in
  `frontend/src/components/simulator-workbench/types.ts` and to `emptySnapshot`.
- `SteeringStatus` shows a clear "No speed data" state when `speed_valid` is false. Keep it to a
  badge/label consistent with the component's existing style — no new components.

## Important constraint: no fake speed source

No CAN decoder for vehicle speed exists yet because no BMW speed frame ID is verified — that is
deliberate (`config.PlaceholderBmwIds` documents candidates only). Therefore in the workbench
`speed_valid` will simply be false, displayed honestly as "no speed data". **Do not** register a
speed decoder, invent a frame ID, or add a simulator API that injects speed directly into the
application (that would bypass the buses, which `docs/simulation.md` forbids). The wiring of a
real speed source is future feature work, not hardening.

## Tasks

1. Application-layer changes (state, config, controller signature + `tick`, snapshot field).
   Update existing tests for the `handle_event(event, now)` signature — this phase is explicitly
   allowed to change that signature; pass literal floats in tests.
2. Runtime changes + tests: a tick with a fake application asserting outputs are sent; staleness
   scenario driven end-to-end with a fake clock (receive speed at t=0 → `speed_valid` true; tick
   at t=0.5 → still true; tick at t=1.5 → false).
3. Simulation clock threading + `SimulatorController.tick` + tests using a fake clock (a tiny
   mutable-time helper in the test file is fine; do not add a library).
4. API background tick task + test (use the existing `TestClient` pattern; assert idle ticks do
   not broadcast, and that the endpoint behaviour is unchanged).
5. Frontend field + display; `pnpm typecheck && pnpm lint`.
6. Update `docs/simulation.md` (workbench behaviour section) and `coordinator/README.md` with
   one or two sentences on the tick path and the no-speed-source status.

## Out of scope

- Steering current computation or PWM output (future feature work — this phase only provides the
  `speed_valid` signal it will consume).
- TX gating and rate limiting (phase 4).
- Any change to what the websocket sends per event beyond the tick broadcast rule (phase 5).

## Acceptance criteria

- No `time.monotonic()` call sites inside `application/`, `simulation/bus.py` logic, or
  `simulation/controller.py` logic — only as parameter defaults.
- The staleness test proves the transition in both directions (fresh → stale → fresh again after
  a new `SpeedUpdateEvent`) using only a fake clock; no `time.sleep` anywhere in tests.
- All checks pass, including frontend typecheck/lint.
