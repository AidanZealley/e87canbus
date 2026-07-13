# Phase 6 — Live runner skeleton

## Goal

Build the minimal live runner: open the configured SocketCAN interfaces, feed every received
frame through the same `CoordinatorRuntime.process_frame` the simulator uses, and call
`runtime.tick()` on the configured interval — with clean shutdown and the phase 4 TX posture
composed in. This replaces the "Live CAN startup is not implemented yet" branch in
`cli/main.py`. It is a skeleton: correct plumbing, boring code, no features.

## Concurrency decision (decided — record it, don't revisit it)

**Threads, not asyncio.** One reader thread per CAN interface using the existing synchronous
`SocketCanBus.receive(timeout_s=...)`, one shared `queue.Queue`, and the main thread as the sole
consumer running frames and ticks.

Rationale to record in the implementation log: `python-can`'s synchronous API is its mature path;
three reader threads plus one consumer is trivially reasoned about and matches the "simplicity
first" charter; the application/runtime stay single-threaded (the queue is the only
synchronization point), so no locks enter application code; asyncio would rewrite the `CanBus`
protocol and the runtime's call signatures for no measurable gain at three buses on a Pi Zero
2W. PROJECT_CONTEXT.md's asyncio note predates this design and is superseded — update it.

## Design (decided — implement as written)

New module `coordinator/src/e87canbus/live.py`:

```python
def read_frames_into_queue(network, bus, frames, stop, receive_timeout_s=0.2) -> None
    # Reader-thread body: loop until stop.is_set(); bus.receive(timeout_s=...);
    # put RoutedCanFrame(network, frame) for each frame. OSError → log warning, continue.

def run_coordinator_loop(runtime, frames, stop, tick_interval_s, clock=time.monotonic) -> None
    # Main loop: runtime.start(); then until stop.is_set():
    #   frames.get(timeout=<time remaining until next tick, floored at a small minimum>)
    #   → runtime.process_frame(...) on a frame, queue.Empty is fine;
    #   when clock() >= next_tick: runtime.tick(); next_tick += tick_interval_s.

def run_live(config: AppConfig) -> int
    # Composition root: for each enabled network open SocketCanBus(config.interface);
    # wrap TX-enabled networks' buses in RateLimitedCanBus(bus, config.tx_policy);
    # build CoordinatorRuntime(buses, tx_networks=frozenset(tx-enabled networks));
    # start reader threads (daemon=True, named after the network);
    # log the posture at startup: "TX enabled: kcan | listen-only: ptcan, fcan";
    # run run_coordinator_loop on the main thread;
    # on KeyboardInterrupt: set stop, join readers (bounded), shut down buses. Return 0.
```

Keep these as three module-level functions — no runner class, no manager object. The first two
are pure enough to unit test without SocketCAN; only `run_live` touches real interfaces, and it
stays thin enough to verify by reading.

Notes:

- `RoutedCanFrame` already exists (`protocol/can.py`); the queue item is exactly that — do not
  invent a new envelope type.
- Tick drift: the `next_tick += tick_interval_s` accumulator keeps average cadence under load;
  if the loop falls more than a few intervals behind, resynchronize `next_tick` to `clock()`
  rather than firing a burst of catch-up ticks — a burst of stale ticks has no value and delays
  frame processing. Comment this constraint on the resync line.
- Interface bring-up (`ip link set can0 up type can bitrate ...`) stays in `scripts/` and docs —
  the runner assumes interfaces exist and fails with a clear log message naming the interface
  when `can.Bus` raises.

### CLI (`cli/main.py`)

- Without `--dry-run`: call `live.run_live(default_config())` instead of printing the
  not-implemented message. Keep `--dry-run` exactly as is.
- Set up `logging.basicConfig` with a `--log-level` argument, matching the pattern in
  `cli/bench_pingpong.py`.

## Tasks

1. Implement `live.py` as designed.
2. Tests (`tests/test_live.py`), all with fake buses (the `FakeBus` pattern from
   `tests/test_runtime.py`) and a fake clock — no SocketCAN, no sleeps beyond tiny real-queue
   timeouts:
   - `read_frames_into_queue`: enqueues routed frames tagged with the right network; stops
     promptly when `stop` is set; a bus raising `OSError` logs and continues.
   - `run_coordinator_loop`: processes queued frames through a real
     `CoordinatorRuntime` + fake buses; fires ticks at the configured cadence under a fake
     clock; the resync rule engages when the clock jumps far ahead (assert one tick, not a
     burst).
   - End-to-end thread test: real threads, real queue, in-memory buses; push a button-event
     frame, assert the LED reply lands on the TX-enabled fake K-CAN bus, then stop and join
     within a bounded timeout.
3. CLI wiring + a test that `main([])` without CAN interfaces fails cleanly (exit code and log
   message) — monkeypatch `run_live` rather than opening sockets.
4. Docs: update `coordinator/README.md` (the "no live runner" sentence),
   `docs/deployment.md` / `docs/coordinator_bootstrap.md` if they reference the CLI, and the
   superseded asyncio note in `PROJECT_CONTEXT.md`'s software architecture section. Add a short
   "Running live" section stating the safety posture: default config is listen-only on PT-CAN
   and F-CAN, TX on K-CAN only, rate-limited; and that `0x700`/`0x701` still require collision
   validation before any in-car transmission (link `protocol/custom_ids.md`).

## Out of scope

- systemd unit changes beyond whatever the CLI rename strictly requires
  (`deploy/systemd/e87canbus.service` — check, adjust only if it invokes a changed entry point).
- Config file / environment loading (defaults-in-code remain; a config-loading pass is future
  work).
- Any feature behaviour. The runner exists so that when features land, live and simulated
  execution differ only in composition.

## Acceptance criteria

- `uv run e87canbus --dry-run` output unchanged; `uv run e87canbus` on a machine without CAN
  interfaces exits non-zero with a clear message naming the missing interface (manual check,
  note result in the log).
- Application and runtime code contain zero threading primitives — threads, queue, and stop
  event live only in `live.py`.
- All tests deterministic and fast (<2 s added); pytest, mypy, ruff pass.
