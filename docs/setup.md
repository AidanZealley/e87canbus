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
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
```

Run the dry-run CLI:

```bash
uv run e87canbus run --mode live --dry-run
```

## Button-pad device

From the PlatformIO project directory:

```bash
cd devices/button-pad
pio run
```

Upload to the button-pad controller connected over USB:

```bash
./scripts/button_pad_upload.sh
```

PlatformIO normally detects the only connected board. To choose a specific USB device, list ports
and pass the selected port through `UPLOAD_PORT`:

```bash
pio device list
UPLOAD_PORT=/dev/cu.usbmodemXXXX ./scripts/button_pad_upload.sh
```

On Linux, the port is commonly `/dev/ttyACM0` or similar.

## Coordinator CAN

Bench SocketCAN defaults target a Raspberry Pi 4 with a Waveshare RS485 CAN HAT v2.1:

- `dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000`
- `can0` at `100000`

Manually bring up bench CAN:

```bash
sudo ./scripts/bench_can_up.sh
```

The bench helper configures only this single 100 kbit/s interface. Three-interface live bring-up
and a live vehicle coordinator process are not part of this milestone.
