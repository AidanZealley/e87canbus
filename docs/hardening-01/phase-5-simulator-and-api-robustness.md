# Phase 5 — Simulator cascade handling and API payload hygiene

## Goal

Three robustness fixes found in review, plus deletion of a dead frontend compatibility branch:

1. The simulator processes cascaded reactions until the buses are quiescent, instead of one pass.
2. The websocket broadcast survives any per-socket failure.
3. Per-command payloads stop carrying the entire trace (up to 2,000 entries of JSON per button
   press); the frontend maintains the trace from the incremental frame events it already
   receives but currently ignores.

## Why

- **Cascades:** `SimulatorController._process_pending` (`simulation/controller.py`) runs
  runtime-drain then device-drain exactly once. Today's devices are passive so nothing is lost,
  but the moment the simulated car *responds* to a frame (the whole point of the simulator's
  future), reactions-to-reactions silently sit in queues until the next user command. That is a
  correctness bug in waiting, and it would make the simulator's behaviour diverge from a live
  bus, where there is no such stall.
- **Broadcast:** `ConnectionManager.broadcast` (`api/simulator.py:36-45`) catches only
  `RuntimeError`. A socket that fails with anything else kills the broadcast loop for every
  other connected client.
- **Payload:** `snapshot_to_dict` inlines the full trace, and a snapshot is broadcast and
  returned on every command. With a busy trace this is O(2,000) JSON objects per button press,
  growing with phase 3's tick outputs and any future simulated car traffic.

## Design (decided — implement as written)

### 1. Quiescence loop (`simulation/controller.py`)

Rework `_process_pending`'s drain section into a bounded loop:

```
for _ in range(MAX_CASCADE_PASSES):          # module constant, 32
    processed = runtime.drain_pending()
    processed += <device processing>          # neotrellis (collect LED updates across passes),
                                              # steering controller, car — all return counts
    if processed == 0:
        break
else:
    LOGGER.warning("simulation did not quiesce after %d passes", MAX_CASCADE_PASSES)
```

`SimulatedNeoTrellisNode.process_pending_led_updates` returns a list — accumulate across passes
so the emitted `led_update` events are complete. The cap is a guard against a future
frame-answering-frame livelock between simulated devices; hitting it is a simulation bug, hence
warn rather than raise.

### 2. Broadcast hardening (`api/simulator.py`)

In `ConnectionManager.broadcast`, wrap each socket's sends in `try/except Exception` and mark
the socket for disconnect on any failure. One failing client must never affect the others.
Keep the method's shape otherwise.

### 3. Trace out of the per-command payload

Backend:

- `snapshot_to_dict(snapshot, *, include_trace: bool)` — explicit keyword, no default, so every
  call site states its intent. The serialized dict simply omits the `"trace"` key when false.
- Full snapshot (`include_trace=True`): `GET /api/snapshot`, the websocket-connect greeting, and
  `POST /api/reset` (its trace is empty; sending it signals "clear yours").
- Slim snapshot (`include_trace=False`): command responses (`press`/`release`/`step`) and their
  broadcast snapshot events, and phase 3's tick broadcasts. The incremental `frame` events (one
  per new trace entry, already emitted in `last_events`) carry the trace deltas.

Frontend (`SimulatorWorkbench.tsx`, `types.ts`, `api/simulator.ts`):

- `SimulatorSnapshot.trace` becomes optional (`trace?: CanTraceEntry[]`).
- `applySnapshot` keeps the existing trace when the payload has none, replaces it when present.
- The websocket handler additionally applies `frame` events: append to the trace, capped at the
  last 2,000 entries (matching the backend's `trace_capacity`), and `led_update` events: update
  `led_colours`. Keep this as a small pure reducer function next to `applySnapshot` so it is
  unit-readable; do not add a state library.
- Delete the "backend is using an older API" branch in `applySnapshot`
  (`SimulatorWorkbench.tsx:62-67`) and the `application` null-check plumbing around it — the
  compatibility window it covered is long past, and phase 1/3 already changed the snapshot shape
  in lockstep with the backend.

Note the REST command responses are also received by `runCommand` and applied via
`applySnapshot` — with a slim snapshot this now correctly leaves the trace alone, and the trace
entries arrive once, via the websocket. One command must not append its frames twice (this is
what the sequence-numbered cap protects; entries are keyed by `sequence`, so make the reducer
ignore a frame whose sequence is already present).

## Tasks

1. Quiescence loop + test: in the test, replace `controller.steering_controller` with a duck-typed
   test double whose `drain_pending` sends a valid button-event frame from its own bus the first
   time it drains something (a reactive device), then assert one `press_button` call fully
   processes the cascade — the double's frame reaches the application within the same command
   (visible in the returned snapshot/trace). For the livelock case, make the double reply every
   time and assert the pass-cap warning fires via `caplog` while the call still returns.
2. Broadcast hardening + test (a fake websocket whose `send_json` raises `ValueError` must not
   prevent delivery to a healthy one — test `ConnectionManager` directly, no server needed).
3. Backend payload split + updates to `tests/test_simulator_api.py` (assert command responses
   contain no `"trace"` key; assert `GET /api/snapshot` and reset still do).
4. Frontend reducer + types + deletion of the compatibility branch. Verify manually against a
   running backend if convenient, and with `pnpm typecheck && pnpm lint` regardless.
5. Update the workbench paragraph in `docs/simulation.md` (it documents that reset clears the
   trace and how events flow).

## Out of scope

- Splitting the simulator-control API from a future live application-state API. Worth doing when
  the in-car UI exists; recorded here so the intent isn't lost, but building a second API surface
  now would be speculative.
- Any change to trace capacity or the trace data model.

## Acceptance criteria

- A button press with 2,000 trace entries present produces a command response and broadcast
  containing zero trace entries (only new `frame` events).
- Frame events arriving over both REST-then-websocket paths never duplicate rows in the
  workbench table (sequence-keyed dedupe test or manual verification noted in the log).
- All checks pass: pytest, mypy, ruff, frontend typecheck + lint.
