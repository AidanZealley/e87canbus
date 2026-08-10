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
K-CAN (`kcan`) as well as being decoded through the coordinator's normal CAN event path, so an
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

## Coordinator panel

The `car` and `bench` profiles require a Raspberry Pi 4 Model B and provision the physical panel
transport and its fixed `e87canbus-hotspot` NetworkManager connection. Pi 5 and other models are
outside this fixed deployment because the UART3 overlay and GPIO allocation are specific to the
Pi 4. Setup validates `/proc/device-tree/model` before making physical-profile changes. On
the post-reboot setup run, the script asks twice for the WPA password without echoing it:

```bash
./scripts/setup_pi.sh --profile bench
```

For unattended first provisioning, put only the password in a file outside the checkout and pass
its path. The file is read directly; the secret is not placed in the command line or service
environment:

```bash
./scripts/setup_pi.sh --profile bench --hotspot-password-file /secure/path/hotspot-password
```

The password must be a single line of 8–63 characters, or exactly 64 hexadecimal digits. A normal
rerun without the option preserves the stored password. Supplying the option again explicitly
replaces it. The `simulator` profile does not request a password or configure UART, NetworkManager,
or panel permissions.

Physical setup enables UART3 as `/dev/ttyAMA3` on BCM4/5, removes the Linux console from the primary
Pi UART, adds the `e87canbus` service account to `dialout`, and installs NetworkManager plus `iw`.
It backs up changed boot files with the `.e87canbus-before-setup` suffix and requires a reboot before
the physical profile starts. The fixed access point uses built-in `wlan0`, is left down with
autoconnect disabled, and assigns the coordinator `10.42.0.1`. Avahi publishes it as `e87.local`.
Once the hotspot is active, a connected laptop can open `http://e87.local/`, or
`http://10.42.0.1/` when mDNS is unavailable, to use any frontend route. A socket-activated proxy
accepts port 80 only on the hotspot address and forwards it to the otherwise loopback-only
controller. The hotspot uses a dedicated policy-routing blackhole so client traffic cannot be
forwarded through an Ethernet default route. A root-owned helper exposes only `activate`,
`deactivate`, `state`, and `stations`; exact sudoers entries let the nologin service account call
those actions without a password. The helper hard-codes `e87canbus-hotspot`, `wlan0`, and every
underlying command, rejects all extra arguments, and provides no connection editing or unrelated
networking operation. The controller unit permits this sudo transition while retaining its other
filesystem and process hardening; the sudoers allowlist remains the effective privilege boundary.

Build the QT Py firmware with PlatformIO:

```bash
cd devices/coordinator-panel
pio run -e qtpy_rp2040
```

Disconnect the complete four-wire Pi harness before connecting QT Py USB-C, then upload from the
repository root:

```bash
./scripts/coordinator_panel_upload.sh
UPLOAD_PORT=/dev/ttyACM0 ./scripts/coordinator_panel_upload.sh
```

The upload uses `picotool` directly, so no firmware file needs to be copied to the `RPI-RP2` drive.
The first upload, or recovery from invalid firmware, may require manually entering the RP2040 USB
bootloader before rerunning the command. USB is only a service and upload connection, not the
installed transport. See
[`devices/coordinator-panel/README.md`](../devices/coordinator-panel/README.md) for the board-specific
bootloader procedure.

After the Pi has rebooted and setup has completed a second time, confirm the deployment without
printing the stored password:

```bash
test -e /dev/ttyAMA3
id e87canbus
tr -d '\0' < /proc/device-tree/model; echo
sudo -u e87canbus sudo -n /usr/local/libexec/e87canbus-hotspot state
sudo -u e87canbus sudo -n -l
nmcli --get-values connection.autoconnect,connection.interface-name \
  connection show id e87canbus-hotspot
```

The sudo listing must show only the four exact helper actions. The coordinator runtime uses the
same executable and one action per invocation; it must never invoke privileged `nmcli` or `iw`
directly.

The remaining bench checks require assembled hardware: UART transmit/receive and one-second
heartbeat, pixel order/colour and perceived brightness, A0 debounce, both firmware link timeouts
and recovery, graceful-off latching, hotspot association and station observation, cancellation of
an in-progress activation, client disconnect on disable, and end-to-end button-to-display
behaviour. Also verify that a client cannot reach an Ethernet uplink.

## Coordinator CAN

The `car` and `bench` Pi profiles require the same three-channel Waveshare stack, configured by
`scripts/setup_pi.sh`:

- `dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000`
- `dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000`
- `dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000`
- `kcan` / K-CAN at `100000`
- `ptcan` / PT-CAN and `fcan` / F-CAN at `500000`

The script also enables SPI1 with three chip selects. It deliberately removes Waveshare's optional
I2C0 overlay because CAN uses SPI and that overlay conflicts with the BTT TFT50 V2.1 touchscreen.
Dedicated service units apply each bitrate and raise all three interfaces automatically at boot.
After a boot configuration change, reboot and rerun setup; it fails closed unless `kcan`, `ptcan`,
and `fcan` map to `spi0.0`, `spi1.1`, and `spi1.2` respectively. The controller remains disabled
during the required reboot and is enabled only after that validation succeeds.

## Capture physical CAN traffic

From an already working bench or car deployment, connect the device and run:

```bash
./scripts/capture_can.sh ccc-knob
```

The script validates that `kcan` is up at 100 kbit/s in normal, ACK-capable mode, temporarily stops
the coordinator to prevent application transmissions, and records until Ctrl-C. It restores the
previous controller-service state on exit. Captures and interface metadata are written beneath
`~/e87canbus-captures/`, outside the Git checkout and immediately accessible after SSH login.
Override that location for a particular run by setting `CAPTURE_ROOT` before invoking the script.
