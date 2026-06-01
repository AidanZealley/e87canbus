# Deployment

Development happens on the host. Pi code deploys over SSH with `rsync`; Arduino firmware uploads from the host through PlatformIO.

## Arduino Upload

Connect the Arduino Micro over USB, then run:

```bash
./scripts/arduino_upload.sh
```

## Pi Deploy

Deploy and restart the systemd service:

```bash
./scripts/pi_deploy.sh pi@e87canbus.local
```

Deploy and tail service logs:

```bash
./scripts/pi_deploy.sh pi@e87canbus.local --tail-logs
```

Before syncing, the deploy script runs:

```bash
uv run pytest
uv run ruff check .
uv run mypy pi/e87canbus
```

It excludes `.git`, `.venv`, `.pio`, and common Python caches, syncs to `/opt/e87canbus`, runs `uv sync` on the Pi, restarts `e87canbus.service`, and prints service status.

## Logs

```bash
./scripts/pi_logs.sh pi@e87canbus.local -f
```

## Acceptance Test

1. Bootstrap the Pi, then reboot.
2. Confirm `can0`:

```bash
ip -details link show can0
```

3. Flash Arduino:

```bash
./scripts/arduino_upload.sh
```

4. Deploy Pi app:

```bash
./scripts/pi_deploy.sh pi@e87canbus.local --tail-logs
```

5. Confirm the Pi logs show alternating press/release button events and green/off LED replies.
6. Confirm the Arduino serial log shows matching sent button events and received LED updates.
