# Hardening Pass 01

A phased hardening of the coordinator, simulator, and API, based on the architectural review of
2026-07-13. The review confirmed the layering is sound and that simulated traffic genuinely routes
through the same `CoordinatorRuntime` / `ProtocolRouter` / `ApplicationController` path intended
for live use. This pass fixes the gaps it found before new features multiply them.

## Goals, in priority order

1. **Safety by architecture, not discipline.** Failsafe behaviour needs a time axis (a silent bus
   produces no callbacks, so a purely frame-driven runtime can never fail safe). Transmission onto
   the car's buses must be denied by default and rate-limited by code, not by convention.
2. **No sprawl.** One source of truth per concept. Feature logic must not accumulate in a growing
   if-chain inside `ApplicationController.handle_event`.
3. **Simulation stays honest.** The simulator must keep routing through the exact same code path as
   live traffic, with a controllable clock so unsafe-to-road-test scenarios become deterministic
   tests.
4. **Code humans can read.** See the code standards below — they are binding for every phase.

## Code standards (binding for all phases)

- **Prefer deletion.** Unused code is a liability; git history preserves it. Do not keep
  speculative stubs "for later".
- **Prefer plain data.** Frozen dataclasses, dicts, and tuples over class hierarchies. No new
  layers or abstractions unless the phase doc explicitly calls for one.
- **Split for readability, not for architecture.** Extract a helper function when it makes the
  caller read like a sentence — not to create indirection.
- **No god functions.** A function that dispatches on many cases becomes a lookup table plus small
  named handlers.
- **Behaviour-preserving unless the phase doc says otherwise.** If existing tests must change,
  the phase doc will say so and why.
- **Match the existing style.** The codebase uses `from __future__ import annotations`, frozen
  dataclasses, `StrEnum`, module-level `LOGGER`, and tests that read as
  arrange / act / assert. Continue it.
- **Comments state constraints, not narration.** Only comment what the code cannot show
  (e.g. why a frame is dropped rather than queued).

## Phases

| # | Doc | Title | Depends on |
|---|---|---|---|
| 1 | [phase-1-dead-code-and-boundaries.md](phase-1-dead-code-and-boundaries.md) | Dead code deletion and boundary cleanup | — |
| 2 | [phase-2-button-dispatch.md](phase-2-button-dispatch.md) | Button dispatch table in the application controller | 1 |
| 3 | [phase-3-time-axis.md](phase-3-time-axis.md) | Time axis: tick, injectable clocks, speed-staleness failsafe | 2 |
| 4 | [phase-4-tx-safety.md](phase-4-tx-safety.md) | Transmit safety: deny-by-default TX and rate limiting | 3 |
| 5 | [phase-5-simulator-and-api-robustness.md](phase-5-simulator-and-api-robustness.md) | Simulator cascade handling and API payload hygiene | 3 |
| 6 | [phase-6-live-runner.md](phase-6-live-runner.md) | Live runner skeleton | 3, 4 |

Phases must be implemented in order (phase 5 and 6 may be swapped; both need 3, and 6 needs 4).

## Workflow

1. Give a fresh agent the contents of [PROMPT.md](PROMPT.md) with the phase number filled in.
2. The agent implements exactly one phase, runs all checks, and appends an entry to
   [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md).
3. Review the diff and the log entry before starting the next phase.

## Checks

Every phase must end with all of these passing:

```bash
uv run pytest -q                  # from repo root
uv run mypy                       # strict; configured in pyproject.toml
uv run ruff check coordinator
```

Phases that touch `frontend/` must also pass:

```bash
cd frontend && pnpm typecheck && pnpm lint
```

## Reference: current architecture map

- `coordinator/src/e87canbus/application/` — authoritative state (`state.py`), internal events
  (`events.py`), and the decision-making `ApplicationController` (`controller.py`). Imports
  nothing above it.
- `coordinator/src/e87canbus/protocol/` — wire-format frame types and codecs (`can.py`), and the
  `ProtocolRouter` (`router.py`) that maps (network, arbitration ID) → application event and
  application output → routed frame.
- `coordinator/src/e87canbus/runtime.py` — transport-neutral `CoordinatorRuntime`; processes one
  `RoutedCanFrame` at a time and dispatches outputs to per-network buses.
- `coordinator/src/e87canbus/live.py` — threaded SocketCAN readers feeding the single-consumer
  runtime loop and periodic ticks.
- `coordinator/src/e87canbus/adapters/socketcan.py` — the only real-hardware CAN adapter.
- `coordinator/src/e87canbus/simulation/` — in-memory broadcast domains (`bus.py`), simulated
  devices (`devices.py`), and the workbench `SimulatorController` (`controller.py`).
- `coordinator/src/e87canbus/api/simulator.py` — FastAPI + WebSocket surface for the browser
  workbench.
- `coordinator/src/e87canbus/config.py` — all typed configuration, plain frozen dataclasses.
- `frontend/src/components/simulator-workbench/` — the React workbench.
- `devices/button-pad/` — bench-only Arduino firmware; `include/can_ids.h` must mirror
  `protocol/custom_ids.md` and `CustomCanIds`.

Import direction (must be preserved): simulation → runtime → protocol → application ← config.
Nothing in `application/` may import `protocol/`, `runtime`, `simulation/`, or `adapters/`.
