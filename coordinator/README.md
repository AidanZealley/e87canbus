# Coordinator

The coordinator is the central Python application deployed to the Raspberry Pi. It owns
authoritative application state and coordinates vehicle inputs, project devices, and the frontend.

## Source map

- `src/e87canbus/application/` — state, events, and application decisions. Start here when changing what the system does.
- `src/e87canbus/features/` — pure steering-assistance calculations.
- `src/e87canbus/protocol/` — CAN frame types plus encoding and decoding.
- `src/e87canbus/runtime.py` — transport-neutral per-frame coordinator runtime.
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
No live three-interface runner or automatic network gateway is included in this milestone.
