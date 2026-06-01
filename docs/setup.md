# Setup

## Python

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run pytest
```

Run lint and type checks:

```bash
uv run ruff check .
uv run mypy pi/e87canbus
```

Run the dry-run CLI:

```bash
uv run e87canbus --dry-run
```

Run the bench ping-pong CLI on the Pi:

```bash
uv run e87canbus-bench-pingpong --interface can0
```

## Arduino

From the PlatformIO project directory:

```bash
cd arduino/neotrellis_node
pio run
```

Upload to an Arduino Micro connected over USB:

```bash
./scripts/arduino_upload.sh
```

## Pi CAN

Bench SocketCAN defaults target a Raspberry Pi 4 with a Waveshare RS485 CAN HAT v2.1:

- `dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000`
- `can0` at `500000`

Bootstrap Raspberry Pi OS Lite with:

```bash
sudo ./scripts/pi_bootstrap.sh --repo-url git@github.com:<owner>/<repo>.git
```

Manually bring up bench CAN:

```bash
sudo ./scripts/bench_can_up.sh
```
