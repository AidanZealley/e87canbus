# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: project scaffold only. The Python package, local tests, CAN protocol notes, and Arduino PlatformIO skeleton are present, but no live CAN transmit, BMW replay, or Servotronic output is implemented.

## Layout

- `pi/e87canbus/` - Python package for Pi-side application logic.
- `pi/tests/` - hardware-free unit tests.
- `arduino/neotrellis_node/` - PlatformIO scaffold for an ATmega32U4 NeoTrellis/CAN node.
- `can/` - project CAN IDs and placeholder DBC notes.
- `docs/` - setup, wiring, decoded-message, and future capture notes.
- `PROJECT_CONTEXT.md` - source project context.

## Local Setup

```bash
uv sync
```

Run the dry-run CLI:

```bash
uv run e87canbus --dry-run
```

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy pi/e87canbus
```

Build the Arduino scaffold:

```bash
cd arduino/neotrellis_node
pio run
```

## Safety Status

Live CAN transmit, DSC replay, high-beam K-CAN commands, and Servotronic PWM/current output are intentionally not implemented yet. Vehicle-specific IDs and payloads must be captured and verified with `candump` before being treated as confirmed.

