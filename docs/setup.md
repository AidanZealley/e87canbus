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
| `bench` | yes | synthetic | SocketCAN (K-CAN, PT-CAN, F-CAN) | vehicle only |
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
coordinator-local because bench retains a K-CAN-only transmit grant even though all three physical
networks are open. The `car` profile does not construct the synthetic source, decoder, or API
surface and has no CAN transmit grant.

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

The `car` and `bench` Pi profiles require the same three-channel Waveshare stack, configured by
`scripts/setup_pi.sh`:

- `dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000`
- `dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000`
- `dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000`
- `can0` / K-CAN at `100000`
- `can1` / PT-CAN and `can2` / F-CAN at `500000`

The script also enables SPI1 with three chip selects and the HAT+ EEPROM's I2C0 overlay. Dedicated
service units apply each bitrate and raise all three interfaces automatically at boot. After a boot
configuration change, reboot and rerun setup; it fails closed unless `can0`, `can1`, and `can2` map
to `spi0.0`, `spi1.1`, and `spi1.2` respectively. The controller remains disabled during the
required reboot and is enabled only after that validation succeeds.

## Coordinator front panel

For `car` and `bench`, `scripts/setup_pi.sh` also enables the primary GPIO UART without disabling
the Pi 4 Bluetooth controller, removes only serial-console kernel arguments, grants the service
account `dialout` access, and validates `/dev/serial0` after reboot. It provisions one fixed
NetworkManager profile:

- UUID `9ec8d6d7-1c26-46aa-a4c8-7af8a1d0f652`
- interface `wlan0`
- SSID `E87-Coordinator`
- address `192.168.50.1/24`
- `connection.autoconnect=no`

The first setup requires `--hotspot-password-file PATH`. Keep that file outside the checkout with
mode `0600`; the script neither prints nor installs it. During initial `nmcli connection add`, the
password exists transiently in that root command's argument list because nmcli has no supported
stdin secret input for profile creation. Run setup only on the trusted Pi with no untrusted local
users, then remove the temporary file. Later runs preserve the stored PSK, reconcile all non-secret
settings, and do not require the password file.

A root-owned helper accepts only the adapter's exact inspect/up/down commands for that UUID, while
the controller continues to run as `e87canbus`. It cannot edit the profile or pass an unrelated UUID
through the helper. `connection.permissions` was not used because NetworkManager ties a restricted
profile to an active login session, which the system service deliberately does not have; granting
general NetworkManager control through Polkit would expose unrelated profiles.

With the QT Py attached by USB and the Pi UART/power harness disconnected, `--flash-panel` builds
and uploads the firmware using the pinned PlatformIO version through `uv tool run`; no global
PlatformIO installation or `pio` PATH entry is required. The source revision and resulting UF2
SHA-256 are recorded at `/var/lib/e87canbus/coordinator-panel-firmware-version`. Follow the
[bench evidence runbook](coordinator-panel/bench-validation.md) before accepting the physical phase.

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
