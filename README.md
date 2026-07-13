# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: the hardware-independent application controller owns runtime state and is exercised through the visual simulator. NeoTrellis button `0` toggles steering mode between Auto and Manual, buttons `1` and `2` select and adjust the remembered manual level, and button `3` toggles a reversible maximum-assistance override. Together these steering controls populate the full top row. The bench CAN ping-pong remains available for hardware validation. BMW CAN IDs, DSC replay, high-beam strobe, Servotronic output, physical Trellis integration, and the in-car touchscreen UI remain out of scope.

## Layout

- `coordinator/` - central Raspberry Pi application and its tests.
- `devices/` - one independently buildable firmware project per physical device.
- `frontend/` - React UI shared by the development simulator and future in-car display.
- `protocol/` - cross-device CAN IDs, payload documentation, and BMW DBC notes.
- `docs/` - setup, wiring, decoded-message, and future capture notes.
- `scripts/` - coordinator deployment, device upload, bootstrap, and CAN helpers.
- `deploy/systemd/` - coordinator systemd unit.
- `PROJECT_CONTEXT.md` - source project context.

The Python package uses the conventional `src` layout. Start in
`coordinator/src/e87canbus/application/` for system behaviour, `features/` for feature
calculations, `protocol/` for CAN encoding, `adapters/` for real hardware, `simulation/` for
virtual hardware, and `api/` for the frontend interface.

## Local Setup

```bash
uv sync
```

Run the dry-run CLI:

```bash
uv run e87canbus --dry-run
```

Run the hardware-free bench simulator:

```bash
uv run e87canbus-sim-bench --cycles 4
```

Run the visual simulator workbench:

```bash
uv run e87canbus-sim-api --reload
cd frontend
pnpm install
pnpm dev
```

Default URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

In the workbench, press NeoTrellis button `0` to toggle the authoritative steering mode. Buttons `1` and `2` enter Manual at the last runtime manual level, then decrement or increment within the configured bounds. Button `3` enters Manual at maximum assistance and pressing it again restores the prior mode and manual level. Pressing `1` or `2` during the maximum override instead returns to Manual at the saved level; the next press adjusts it normally. The mode LED is blue for Auto or amber for Manual, while button `3` is white when its override is active. Manual level memory is currently process-local and is reset on coordinator or Pi restart.

Run the bench ping-pong app on a Pi with `can0` up:

```bash
uv run e87canbus-bench-pingpong --interface can0
```

## Bench Workflow

Bootstrap a Raspberry Pi OS Lite coordinator:

```bash
sudo ./scripts/coordinator_bootstrap.sh --repo-url git@github.com:<owner>/<repo>.git
```

Upload button-pad firmware from the host:

```bash
./scripts/button_pad_upload.sh
```

Deploy coordinator code and restart the service:

```bash
./scripts/coordinator_deploy.sh pi@e87canbus.local --tail-logs
```

See `docs/bench.md`, `docs/simulation.md`, `docs/coordinator_bootstrap.md`, and `docs/deployment.md`.

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy coordinator/src/e87canbus
bash -n scripts/*.sh
```

Build the frontend:

```bash
cd frontend
pnpm build
```

Build the button-pad firmware:

```bash
cd devices/button-pad
pio run
```

## Safety Status

Live CAN transmit, DSC replay, high-beam K-CAN commands, and Servotronic PWM/current output are intentionally not implemented yet. Vehicle-specific IDs and payloads must be captured and verified with `candump` before being treated as confirmed.
