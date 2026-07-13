# Coordinator

The coordinator is the central Python application deployed to the Raspberry Pi. It owns
authoritative application state and coordinates vehicle inputs, project devices, and the frontend.

## Source map

- `src/e87canbus/application/` — state, events, and application decisions. Start here when changing what the system does.
- `src/e87canbus/features/` — pure steering-assistance calculations.
- `src/e87canbus/protocol/` — CAN frame types plus encoding and decoding.
- `src/e87canbus/runtime.py` — transport-neutral per-frame and periodic-tick coordinator runtime.
- `src/e87canbus/live.py` — threaded SocketCAN readers and the single-consumer live loop.
- `src/e87canbus/adapters/` — integrations with real hardware or operating-system services.
- `src/e87canbus/simulation/` — in-memory CAN and virtual device implementations.
- `src/e87canbus/api/` — HTTP and WebSocket interface used by the frontend.
- `src/e87canbus/cli/` — executable entry points and bench utilities.
- `tests/` — tests arranged to mirror the source responsibilities.

The outer `coordinator/` directory names the deployable component. The inner `src/e87canbus/`
directory is the project-specific import namespace, following Python's conventional `src` layout.
This is why code imports `e87canbus.application` even though it is deployed as the coordinator.

The runtime receives buses keyed by K-CAN, PT-CAN, and F-CAN. Protocol decoding is keyed by both
network and arbitration ID, while application code remains independent of physical bus selection.
Frames and periodic ticks dispatch application outputs through the same runtime path. Speed data is
marked invalid after its configured timeout; no verified BMW speed decoder is configured yet. The
coordinator does not automatically forward frames between networks. Runtime transmission is denied
by default and explicitly enabled per network with `tx_enabled`, behind the limits in `tx_policy`.

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
