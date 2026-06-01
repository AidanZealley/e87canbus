# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: bench CAN ping-pong. The Arduino sends project button-event frames, the Pi receives them through SocketCAN, and the Pi replies with LED-update frames. BMW CAN IDs, DSC replay, high-beam strobe, Servotronic output, Trellis UI, and touchscreen UI remain out of scope.

## Layout

- `pi/e87canbus/` - Python package for Pi-side application logic.
- `pi/tests/` - hardware-free unit tests.
- `arduino/neotrellis_node/` - PlatformIO scaffold for an ATmega32U4 NeoTrellis/CAN node.
- `can/` - project CAN IDs and placeholder DBC notes.
- `docs/` - setup, wiring, decoded-message, and future capture notes.
- `scripts/` - host deploy, Arduino upload, Pi bootstrap, and CAN interface helpers.
- `deploy/systemd/` - Pi systemd unit.
- `PROJECT_CONTEXT.md` - source project context.

## Local Setup

```bash
uv sync
```

Run the dry-run CLI:

```bash
uv run e87canbus --dry-run
```

Run the bench ping-pong app on a Pi with `can0` up:

```bash
uv run e87canbus-bench-pingpong --interface can0
```

## Bench Workflow

Bootstrap a Raspberry Pi OS Lite install:

```bash
sudo ./scripts/pi_bootstrap.sh --repo-url git@github.com:<owner>/<repo>.git
```

Upload Arduino firmware from the host:

```bash
./scripts/arduino_upload.sh
```

Deploy Pi code and restart the service:

```bash
./scripts/pi_deploy.sh pi@e87canbus.local --tail-logs
```

See `docs/bench.md`, `docs/pi_bootstrap.md`, and `docs/deployment.md`.

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy pi/e87canbus
bash -n scripts/*.sh
```

Build the Arduino scaffold:

```bash
cd arduino/neotrellis_node
pio run
```

## Safety Status

Live CAN transmit, DSC replay, high-beam K-CAN commands, and Servotronic PWM/current output are intentionally not implemented yet. Vehicle-specific IDs and payloads must be captured and verified with `candump` before being treated as confirmed.
