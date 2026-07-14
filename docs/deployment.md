# Deployment

Development happens on the host. Coordinator code deploys to the Pi over SSH with `rsync`; device firmware uploads from the host through PlatformIO.

## Button-pad Upload

Connect the button-pad controller over USB, then run:

```bash
./scripts/button_pad_upload.sh
```

The uploaded milestone firmware automatically emits a test frame every second. It is bench-only;
never attach it to the vehicle CAN wiring.

## Coordinator Deploy

Deploy and restart the systemd service:

```bash
./scripts/coordinator_deploy.sh pi@e87canbus.local
```

Deploy and tail service logs:

```bash
./scripts/coordinator_deploy.sh pi@e87canbus.local --tail-logs
```

Before syncing, the deploy script runs:

```bash
uv run pytest
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
```

It excludes `.git`, `.venv`, `.pio`, and common Python caches, syncs to `/opt/e87canbus`, runs `uv sync` on the Pi, restarts `e87canbus.service`, and prints service status.

The current systemd unit remains the isolated `can0` bench ping-pong service. To exercise the live
three-interface runner manually after bringing up all configured interfaces, run
`uv run e87canbus`. The default live composition disables application transmission on K-CAN,
PT-CAN, and F-CAN. This does not put SocketCAN or the CAN controller into kernel/hardware
listen-only mode; configure that separately before an in-car observation session.
K-CAN transmission is enabled only in the isolated simulator and bench commands. Their provisional
`0x700`/`0x701` messages require collision validation before any future live grant. `0x701` is a
DLC-8 packed snapshot of all 16 logical LED colours; one accepted frame replaces the complete
button-pad state. Its writes share the holistic per-network coordinator budget with every other ID,
and physical NeoTrellis rendering remains gated on verified topology and electrical evidence.

## Logs

```bash
./scripts/coordinator_logs.sh pi@e87canbus.local -f
```

## Acceptance Test

This acceptance test is for an isolated, correctly terminated bench at 100 kbit/s only.

1. Bootstrap the Pi, then reboot.
2. Confirm `can0`:

```bash
ip -details link show can0
```

3. Flash the button-pad controller:

```bash
./scripts/button_pad_upload.sh
```

4. Deploy the coordinator:

```bash
./scripts/coordinator_deploy.sh pi@e87canbus.local --tail-logs
```

5. Confirm the Pi logs show alternating complete green/off LED snapshots in response to the button
   events.
6. Confirm the button-pad serial log shows matching sent button events and complete 16-colour LED
   snapshots.
