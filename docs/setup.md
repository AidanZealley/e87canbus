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
uv run e87canbus run --profile car --dry-run
```

The closed deployment profiles are:

| Profile | Physical button pad | Vehicle telemetry | Transport | Development controls |
|---|---|---|---|---|
| `car` | yes | physical | SocketCAN | none |
| `bench` | yes | synthetic | SocketCAN K-CAN | vehicle only |
| `simulator` | emulated | synthetic | in-memory CAN | full workbench |

Profiles choose the complete composition; they cannot be combined with per-device or per-network
CLI overrides.

In the `bench` profile, vehicle readings can be driven from another terminal while the Pi kiosk
continues to display `/car`:

```bash
curl -X PUT http://127.0.0.1:8000/api/dev/simulation/vehicle/speed \
  -H 'Content-Type: application/json' -d '{"speed_kph":42.5}'
curl -X PUT http://127.0.0.1:8000/api/dev/simulation/vehicle/rpm \
  -H 'Content-Type: application/json' -d '{"rpm":3500}'
```

The selected readings are refreshed on every controller timer until their corresponding
`/silence` endpoint is called. In the bench profile, synthetic speed is encoded onto physical
K-CAN (`can0`) as well as being decoded through the coordinator's normal CAN event path, so an
external bench controller can observe the same frame. Other synthetic engine readings remain
coordinator-local because their realistic PT-CAN network is not present in the single-interface
bench. The `car` profile does not construct the synthetic source, decoder, or API surface and has
no CAN transmit grant.

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

The `car` and `bench` Pi profiles use the boot-managed `can0` unit installed by
`scripts/setup_pi.sh`:

- `dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000`
- `can0` at `100000`

The service unit applies the bitrate and raises `can0` automatically at boot. If you change the
boot overlay, reboot and rerun the setup script so the deployed service and CAN interface stay in
sync.

Three-interface live bring-up and a live vehicle coordinator process are not part of this milestone.

## Capture physical CAN traffic

From an already working bench or car deployment, connect the device and run:

```bash
./scripts/capture_can.sh ccc-knob
```

The script validates that `can0` is up at 100 kbit/s in normal, ACK-capable mode, temporarily stops
the coordinator to prevent application transmissions, and records until Ctrl-C. It restores the
previous controller-service state on exit. Captures and interface metadata are written beneath
`~/e87canbus-captures/`, outside the Git checkout and immediately accessible after SSH login.
Override that location for a particular run by setting `CAPTURE_ROOT` before invoking the script.
