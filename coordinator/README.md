# Coordinator

The coordinator is the central Python application deployed to the Raspberry Pi. It owns
authoritative application state and coordinates vehicle inputs, project devices, and the frontend.

## Source map

- `src/e87canbus/application/` — state, events, and application decisions. Start here when changing what the system does.
- `src/e87canbus/features/` — pure steering-assistance calculations.
- `src/e87canbus/protocol/` — CAN frame types plus encoding and decoding.
- `src/e87canbus/runtime.py` — single-owner kernel, ordered input values, commits, and diagnostics.
- `src/e87canbus/live.py` — threaded SocketCAN readers and the single-consumer live loop.
- `src/e87canbus/adapters/` — integrations with real hardware or operating-system services.
- `src/e87canbus/simulation/` — in-memory CAN and virtual device implementations.
- `src/e87canbus/api/` — HTTP and WebSocket interface used by the frontend.
- `src/e87canbus/cli/` — executable entry points and bench utilities.
- `tests/` — tests arranged to mirror the source responsibilities.

The outer `coordinator/` directory names the deployable component. The inner `src/e87canbus/`
directory is the project-specific import namespace, following Python's conventional `src` layout.
This is why code imports `e87canbus.application` even though it is deployed as the coordinator.

The kernel's `dispatch` method is the only application-state mutation path. Startup, received frames,
periodic timers, reader and effect faults, inbox overflow, and shutdown all carry explicit times into
that ordered path. Each decoded event runs through a pure transition; the kernel commits the returned
state and revision before the calling composition executes the commit's ordered effects. Unknown CAN
traffic creates no application commit. Reader, effect, and inbox-overflow faults update immutable
per-network diagnostics; the live runner consumes fatal health and exits non-zero. Speed data is
marked invalid after its configured timeout; no verified BMW speed decoder is configured yet.

The coordinator does not automatically forward frames between networks. Transmission is denied by
the absence of a safe transmitter capability and explicitly granted per network with `tx_enabled`.
Every granted write passes the holistic per-network window in `tx_policy`. Live reader threads only
receive, timestamp, and enqueue into the configured bounded inbox; the main thread alone dispatches
kernel inputs and executes effects. Queue latency is logged without changing observation time.
Overflow, a repeatedly failing reader, or an effect I/O failure becomes visible kernel health and
stops the runner with a non-zero result.

The browser simulator has a separate bounded command queue. One asynchronous owner serializes
button-device commands, control timers, resets, kernel commits, and WebSocket publication. Browser
snapshots expose the kernel revision plus a simulation session ID, and incremental trace frames use
the session ID with their reset-local sequence number.

The provisional custom protocol is defined in `protocol/custom.toml`. Its generator owns the Python
wire constants, firmware header, and marked Markdown tables; `--check` and the test suite reject
single-artifact drift in IDs, lengths, byte positions, state values, or colour codes.

## Running live

Bring up every enabled SocketCAN interface at its configured bitrate, then run:

```bash
uv run e87canbus
```

The default configuration opens all three networks with application transmission disabled. It does
not claim SocketCAN kernel or hardware listen-only mode; configure that separately as an additional
deployment defense. K-CAN transmission is granted only by the isolated simulator and bench
compositions. Custom IDs `0x700` and `0x701` still require collision validation before any future
in-car transmission grant; see [the custom CAN ID registry](../protocol/custom_ids.md). Use
`--log-level` to change logging verbosity. `uv run e87canbus --dry-run` prints the configuration
without opening CAN interfaces.

Phase 8 steering failsafe work cannot begin until speed frames and the actuator boundary are backed
by named captures and hardware evidence. Placeholder candidate IDs remain non-executable.
