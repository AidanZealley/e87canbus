# Fresh Raspberry Pi deployment

This is the canonical start-to-finish procedure for turning a blank Raspberry Pi into the
three-network E87 bench controller. Follow it in order. The commands assume the hostname
`e87-coordinator`, the login user `e87`, the `bench` profile, and headless Raspberry Pi OS Lite
(64-bit).

The finished Pi runs one controller service and three SocketCAN interfaces:

| Interface | Physical connector | SPI device | Bitrate |
|---|---|---|---:|
| `can0` | Original RS485 CAN HAT | `spi0.0` | 100 kbit/s |
| `can1` | 2-CH CAN HAT+ CAN0 | `spi1.1` | 500 kbit/s |
| `can2` | 2-CH CAN HAT+ CAN1 | `spi1.2` | 500 kbit/s |

The service binds to loopback and serves the frontend, HTTP API, and Socket.IO transport from the
same origin. It is unauthenticated and must not be changed to a non-loopback bind without a separate
security decision.

## 1. Prepare the hardware

You need:

- A Raspberry Pi with a 40-pin header, microSD card, and suitable official-quality power supply.
- The Waveshare 2-CH CAN HAT+.
- The original Waveshare RS485 CAN HAT v2.1 with its `12000` oscillator marking.
- Correct standoffs and spacers.
- Another computer on the same network, with Raspberry Pi Imager and an SSH client.

With every power source disconnected:

1. Set the 2-CH CAN HAT+ logic-level jumper to **3.3V**.
2. Leave its factory selections at SPI1 CE1/CE2 and interrupts BCM22/BCM13.
3. Fit the 2-CH CAN HAT+ directly to the Pi.
4. Stack the original RS485 CAN HAT above it.
5. Secure both boards with standoffs and check that no terminal block or solder joint can touch the
   Pi or the other HAT.
6. Leave CAN-H, CAN-L, CAN ground, the HAT+ 7–36V input, and all other external wiring disconnected.
7. Power the first software bring-up only from the Pi's normal power connector.

Do not power the Pi simultaneously from its normal connector and the HAT+ external input unless the
power path has been separately verified. Termination, grounding, and external CAN wiring are tested
only after the three controllers pass the software checks below. See
[the three-channel stack design](../docs/waveshare-three-channel-stack.md) for why this combination
works and [the wiring notes](../docs/wiring.md) for the maintained network assignments.

## 2. Image the microSD card

In Raspberry Pi Imager:

1. Select the correct Raspberry Pi model.
2. Select **Raspberry Pi OS Lite (64-bit)**. This is the expected headless deployment image.
3. Select the microSD card.
4. Open OS customisation and set:
   - Hostname: `e87-coordinator`
   - Username: `e87`
   - A unique password
   - Wi-Fi SSID/password when Ethernet will not be used
   - The correct locale, keyboard, and timezone
   - SSH enabled with password authentication
5. Write and verify the card.
6. Insert it into the unpowered Pi, connect Ethernet if used, and apply power.

Keep the password available until SSH key authentication has been configured separately.

## 3. Make the first SSH connection

Allow a few minutes for the first boot, then run this from the other computer:

```bash
ssh e87@e87-coordinator.local
```

Accept the host fingerprint only when this is the Pi you just imaged, then enter the password. If
`.local` discovery is unavailable, find the address in the router's client list and use
`ssh e87@<pi-address>`.

Confirm the machine and 64-bit operating system:

```bash
hostname
uname -m
grep -E '^(PRETTY_NAME|VERSION_CODENAME)=' /etc/os-release
```

Expected essentials are hostname `e87-coordinator`, architecture `aarch64`, and a supported
Raspberry Pi OS release.

## 4. Update the operating system

```bash
sudo apt update
sudo apt full-upgrade -y
```

Reboot after the upgrade:

```bash
sudo reboot
```

The SSH session will close. Wait for the Pi to return, then reconnect:

```bash
ssh e87@e87-coordinator.local
```

## 5. Clone the repository at its required path

Install Git, create the deployment directory with the login user as owner, and clone the public
repository:

```bash
sudo apt install -y git
sudo install -d -o "$(id -un)" -g "$(id -gn)" /opt/e87canbus
git clone https://github.com/AidanZealley/e87canbus.git /opt/e87canbus
cd /opt/e87canbus
git remote -v
git status --short
```

The remote should be `https://github.com/AidanZealley/e87canbus.git`, and `git status --short`
should print nothing. Do not run the setup script with `sudo`; it deliberately uses `sudo` only for
the system changes it owns.

## 6. Run setup for the first time

```bash
cd /opt/e87canbus
./scripts/setup_pi.sh --profile bench
```

Enter the `e87` password when `sudo` requests it. This run installs host dependencies, synchronizes
the Python environment, builds the frontend, configures SPI0/SPI1 and the three MCP2515 controllers,
installs the CAN/controller/kiosk services, and disables controller autostart until the hardware
mapping has been validated.

On a fresh installation it should finish by saying that boot configuration changed and that a
reboot is required. It should show this rerun command:

```text
cd /opt/e87canbus && ./scripts/setup_pi.sh --profile bench
```

If the script exits with an error instead, do not reboot past it without reading the error. Resolve
package, build, or filesystem failures first.

## 7. Reboot into the CAN configuration

```bash
sudo reboot
```

Wait for the Pi to return and reconnect:

```bash
ssh e87@e87-coordinator.local
```

## 8. Run setup a second time

```bash
cd /opt/e87canbus
./scripts/setup_pi.sh --profile bench
```

The second run must print all three confirmations before it starts the controller:

```text
Validated can0 -> spi0.0
Validated can1 -> spi1.1
Validated can2 -> spi1.2
```

It then starts the three CAN services, enables the controller for subsequent boots, and prints
`Pi setup complete`. Missing interfaces or a different SPI mapping deliberately leave the
controller stopped and disabled.

## 9. Confirm the installation

Check the kernel-to-hardware mapping independently:

```bash
for interface in can0 can1 can2; do
    printf '%s -> ' "${interface}"
    basename "$(readlink -f "/sys/class/net/${interface}/device")"
done
```

Expected output:

```text
can0 -> spi0.0
can1 -> spi1.1
can2 -> spi1.2
```

Confirm the configured bitrates:

```bash
ip -details link show can0 | grep -o 'bitrate [0-9]*'
ip -details link show can1 | grep -o 'bitrate [0-9]*'
ip -details link show can2 | grep -o 'bitrate [0-9]*'
```

Expected output, in order:

```text
bitrate 100000
bitrate 500000
bitrate 500000
```

All four services must be active:

```bash
systemctl is-active \
    e87canbus-can0.service \
    e87canbus-can1.service \
    e87canbus-can2.service \
    e87canbus-controller.service
```

Expected output is four lines containing `active`. Finally, both health checks must succeed:

```bash
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
```

At this point the fresh Pi installation is complete. These checks prove the Pi can communicate with
all three MCP2515 controllers and that the application is running. They do not yet prove external
CAN transceiver wiring, termination, grounding, or traffic.

## 10. Bring up the bench buses safely

Connect and validate one physical CAN network at a time. Before changing bench wiring, stop the
application so it cannot use its bench K-CAN transmit grant:

```bash
sudo systemctl stop e87canbus-controller.service
```

With every node powered off, set termination appropriate to that individual bus. A bus with two
120Ω endpoint terminators measures approximately 60Ω between CAN-H and CAN-L. Do not add a third
terminator when tapping an already terminated network. Confirm CAN-H to CAN-H, CAN-L to CAN-L, and
the required reference-ground arrangement before applying power.

Observe each connected bus in its own SSH session:

```bash
candump -tz can0
candump -tz can1
candump -tz can2
```

`candump` waits silently when there is no traffic. Receiving valid frames proves more of the path
than interface creation alone; transmit/ACK testing additionally requires another correctly wired
and configured node. Restart the application after the bench wiring is known-good:

```bash
sudo systemctl restart e87canbus-controller.service
curl --fail http://127.0.0.1:8000/health/ready
```

## Troubleshooting

### SSH does not connect

- Confirm the Pi has power and completed its first boot.
- Try its router-assigned address instead of `e87-coordinator.local`.
- Confirm SSH was enabled in Raspberry Pi Imager.
- If a re-imaged Pi reports a changed host key, verify the new Pi locally before removing the old
  entry from the other computer's `known_hosts` file.

### Setup rejects the checkout location or user

The repository must be exactly `/opt/e87canbus`, owned by the invoking login user, and the command
must be `./scripts/setup_pi.sh`, not `sudo ./scripts/setup_pi.sh`.

```bash
cd /opt/e87canbus
pwd
id
git status --short
```

### A CAN interface is missing or maps to the wrong SPI device

Leave the controller stopped. Check the HAT seating, the HAT+ 3.3V logic jumper, its factory
chip-select/interrupt resistor selections, and the original HAT's `12000` marking. Then inspect:

```bash
grep -E '^(dtparam=spi|dtoverlay=(i2c0|spi1|mcp2515))' /boot/firmware/config.txt 2>/dev/null \
    || grep -E '^(dtparam=spi|dtoverlay=(i2c0|spi1|mcp2515))' /boot/config.txt
sudo dmesg | grep -Ei 'mcp251|spi[01]|can'
```

The managed boot lines are documented in [the setup reference](../docs/setup.md#coordinator-can).
After correcting hardware or configuration, fully remove power once, boot, and rerun the setup
script.

### A CAN or controller service fails

```bash
systemctl --no-pager --full status \
    e87canbus-can0.service \
    e87canbus-can1.service \
    e87canbus-can2.service \
    e87canbus-controller.service
journalctl -b -u e87canbus-can0.service -u e87canbus-can1.service \
    -u e87canbus-can2.service -u e87canbus-controller.service
```

The controller requires all three CAN services on physical installations, so a CAN bootstrap
failure intentionally prevents a working physical deployment.

### A health check fails

```bash
journalctl -b -u e87canbus-controller.service --no-pager
systemctl --no-pager --full status e87canbus-controller.service
```

`/health/live` proves the ASGI event loop responds. `/health/ready` returns success only after the
database, controller, and publisher have started; it returns `503` during fatal failure or shutdown.

## Bench and car profiles

Both physical profiles require the same complete three-interface stack. The bench profile opens all
three physical networks, exposes synthetic vehicle development controls, and retains a K-CAN-only
application transmit grant. The car profile exposes no development controls and grants no
application CAN output. The simulator profile uses no physical CAN interfaces.

Always write the intended profile explicitly:

```bash
./scripts/setup_pi.sh --profile bench
./scripts/setup_pi.sh --profile car
./scripts/setup_pi.sh --profile simulator
```

## Kiosk display

The expected Raspberry Pi OS Lite installation is headless. The setup script installs Cage as a
system service and configures the display-access groups, quiet boot, and Plymouth splash. A display
may be attached locally later; no desktop environment or desktop login is required.

Raspberry Pi OS Desktop remains an optional supported alternative. When a display manager is
detected, setup uses a desktop autostart entry instead of Cage; Desktop Autologin must then be
enabled separately under `sudo raspi-config` → System Options → Boot / Auto Login.

Both modes install the same kiosk launcher at `/usr/local/bin/e87canbus-kiosk`. It waits for
`/health/live` before opening Chromium at the local `/car` route.

## Routine operation

```bash
systemctl status e87canbus-controller.service
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
journalctl -u e87canbus-controller.service -f
sudo systemctl restart e87canbus-controller.service
sudo systemctl stop e87canbus-controller.service
```

Logs are written to the journal. A fatal controller exit returns nonzero and systemd waits five
seconds before restarting it. The complete failure policy and simulated soak evidence are in
[the reliability notes](../docs/reliability.md).

## Update and rollback

For an ordinary code update:

```bash
cd /opt/e87canbus
git status --short
git pull --ff-only
./scripts/setup_pi.sh --profile bench
```

Do not pull over unexplained local changes. Before an update that changes persistence, stop the
controller and back up `/var/lib/e87canbus/application.sqlite3` together with any matching `-wal`
and `-shm` files. A rollback must restore a matching application revision and database set together.
Durable settings and profiles live in that SQLite database; live telemetry and traces are
process-local and are not restored.
