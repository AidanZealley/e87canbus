# Fresh Raspberry Pi 4 deployment

This is the canonical blank-Pi runbook for the two supported hosts. Both use Raspberry Pi 4 Model
B hardware, Raspberry Pi OS, the repository at `/opt/e87canbus`, and a direct Ethernet cable. The
coordinator is headless near the junction box; the console owns the screen and kiosk.

| Host | CAN hardware | Frontend | Main service | Setup command |
|---|---|---|---|---|
| Coordinator | Original RS485 CAN HAT plus 2-CH CAN HAT+: `kcan`, `ptcan`, `fcan` | `frontend/apps/coordinator/dist` | `e87canbus-controller.service` | `./scripts/setup_coordinator.sh --profile car` |
| Console | 2-CH CAN HAT+ CAN0 only: application receive-only `kcan`; CAN1 disconnected | `frontend/apps/console/dist` | `e87canbus-console.service` | `./scripts/setup_console.sh --profile car` |

The hosts use `10.43.0.0/30`: coordinator `10.43.0.1`, console `10.43.0.2`. The NetworkManager
connection has no gateway or DNS, is never a default route, and uses an ingress blackhole to
prevent forwarding. The coordinator application remains on `127.0.0.1:8000`; a socket-activated
proxy exposes it only at `10.43.0.1:80` on `eth0`. The console application, local Socket.IO
endpoint and frontend remain on its own `127.0.0.1:8000`. The console frontend contacts the
coordinator at `http://10.43.0.1`.

## Common preparation

With all power disconnected, assemble the HATs for the chosen role. Set the 2-CH CAN HAT+ logic
jumper to 3.3 V and leave its factory SPI1 CE1/CE2 selections. On the console, leave CAN1 entirely
disconnected and leave CAN0's 120-ohm termination disabled when tapping the already terminated
vehicle K-CAN. Do not connect vehicle CAN or the HAT+ 7-36 V input during initial software setup.
See [wiring](../docs/wiring.md) and the
[three-channel coordinator stack](../docs/waveshare-three-channel-stack.md).

Image Raspberry Pi OS for a Raspberry Pi 4, enable SSH, create login user `e87`, and use hostname
`e87-coordinator` or `e87-console` as appropriate. For the console, choose an image/display setup
that supports the intended touchscreen; the installer supports either an existing desktop display
manager or a headless OS with Cage.

After the first boot, connect by SSH and prepare the fixed checkout:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y git
sudo install -d -o "$(id -un)" -g "$(id -gn)" /opt/e87canbus
git clone https://github.com/AidanZealley/e87canbus.git /opt/e87canbus
cd /opt/e87canbus
git status --short
```

Run setup as the checkout owner, not with `sudo`. Each installer uses `sudo` only for the system
changes it owns. The first run normally changes boot configuration and asks for a reboot. Reboot,
then rerun the same command; the second run validates hardware before enabling application
services.

## Coordinator installation

The physical coordinator supports the existing `car` and `bench` controller profiles. `car` is the
production default and has no application CAN transmit grant; `bench` retains its existing bounded
K-CAN test grant and development controls. `simulator` is available for non-physical development
and installs no CAN, hotspot or console-link proxy services.

For a production coordinator:

```bash
cd /opt/e87canbus
./scripts/setup_coordinator.sh --profile car
sudo reboot
cd /opt/e87canbus
./scripts/setup_coordinator.sh --profile car
```

The post-reboot physical run asks twice for the coordinator hotspot password. For unattended
provisioning, pass a single-line password file stored outside the checkout:

```bash
./scripts/setup_coordinator.sh --profile car \
  --hotspot-password-file /secure/path/hotspot-password
```

A normal rerun without that option preserves the stored password. Supply `--reboot` if setup
should reboot automatically after a boot-file change.

Setup must validate these mappings before starting the controller:

```text
kcan  -> spi0.0, 100000 bit/s
ptcan -> spi1.1, 500000 bit/s
fcan  -> spi1.2, 500000 bit/s
```

Confirm the coordinator services and addresses:

```bash
systemctl is-active e87canbus-kcan.service e87canbus-ptcan.service \
  e87canbus-fcan.service e87canbus-controller.service \
  e87canbus-coordinator-hotspot-proxy.socket \
  e87canbus-coordinator-console-proxy.socket
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
ip -4 address show dev eth0
sudo -u e87canbus sudo -n /usr/local/libexec/e87canbus-hotspot state
sudo -u e87canbus sudo -n -l
```

The fixed hotspot remains `10.42.0.1/24`; its proxy is separate from the console-link proxy. The
sudo listing must contain only the four exact hotspot-helper actions. The coordinator installs no
kiosk, display service, console service or console frontend.

## Console installation

Fit only the Waveshare 2-CH CAN HAT+. CAN0 is the first controller at `spi1.1`; CAN1 at `spi1.2`
must remain disconnected. The installer deliberately creates no overlay, udev name or service for
CAN1.

```bash
cd /opt/e87canbus
./scripts/setup_console.sh --profile car
sudo reboot
cd /opt/e87canbus
./scripts/setup_console.sh --profile car
```

The post-reboot run validates `kcan -> spi1.1`, builds only the console frontend, configures the
fixed Ethernet link, and installs the local CAN, application and kiosk services. Kernel
listen-only mode is the default `car` profile and is independent of the application's receive-only
capability. On an isolated coordinator-console bench, select `--profile bench` on both setup runs.
This keeps the console application receive-only but lets its CAN controller acknowledge valid
frames; never use the bench console profile as a passive vehicle-bus tap.

Confirm the console:

```bash
systemctl is-active e87canbus-console-kcan.service e87canbus-console.service
systemctl is-active e87canbus-console-kiosk.service  # headless/Cage installation only
ip -details link show kcan
ip -4 address show dev eth0
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
curl --fail http://10.43.0.1/health/live
```

`ip -details link show kcan` must report bitrate `100000`; it reports `listen-only on` for `car` and
omits that flag for `bench`. The local health
endpoint proves the console process is responsive; readiness requires its CAN reader to be
connected. The K-CAN activity display is an end-to-end diagnostic proof only: it publishes
connection state, a bounded frame count and faults, never arbitration IDs, payload bytes or decoded
vehicle features.

On an OS without a display manager, setup installs Cage and
`e87canbus-console-kiosk.service`. With an existing display manager it instead installs
`~/.config/autostart/e87canbus-console-kiosk.desktop`; enable desktop autologin separately. Both
launch `http://127.0.0.1:8000/` after the local console health check succeeds.

## Dedicated Ethernet checks

With the direct cable attached, confirm the fixed addresses and local reachability:

```bash
# Coordinator
ip route show dev eth0
ss -ltn 'sport = :80'

# Console
ip route show dev eth0
curl --fail http://10.43.0.1/health/live
```

Neither host should have a gateway or DNS assigned by `e87canbus-console-link`. Do not enable IP
forwarding or internet sharing. Confirm separately on the assembled pair that traffic arriving on
the console link cannot be forwarded to the coordinator hotspot or another uplink.

## Bench CAN bring-up

Connect and validate one bus at a time with all nodes powered off while changing wiring. A bus
with two 120-ohm endpoint terminators normally measures about 60 ohms between CAN-H and CAN-L. Do
not add another terminator when tapping a vehicle bus.

On the coordinator, stop the controller before capture so bench output cannot occur:

```bash
sudo systemctl stop e87canbus-controller.service
candump -tz kcan
candump -tz ptcan
candump -tz fcan
```

On a car-profile console, keep the managed listen-only service active and observe K-CAN:

```bash
ip -details link show kcan
candump -tz kcan
```

Receiving frames proves more than interface creation, but not vehicle-safe power, grounding,
termination, transceiver compatibility or reliable operation across disturbances.

## Routine operation

Coordinator:

```bash
systemctl status e87canbus-controller.service
journalctl -u e87canbus-controller.service -f
sudo systemctl restart e87canbus-controller.service
```

Console:

```bash
systemctl status e87canbus-console.service e87canbus-console-kcan.service
journalctl -u e87canbus-console.service -f
sudo systemctl restart e87canbus-console.service
```

For updates, require a clean checkout, pull fast-forward-only, and rerun the appropriate setup
script. Before coordinator updates that affect persistence, stop the controller and back up
`/var/lib/e87canbus/application.sqlite3` together with matching `-wal` and `-shm` files.

## Troubleshooting

Inspect failed units with `systemctl --no-pager --full status UNIT` and `journalctl -b -u UNIT`.
If a CAN mapping is wrong, leave the application stopped, check HAT seating, jumper and oscillator
markings, inspect the boot overlays and `dmesg`, then power-cycle and rerun setup. The coordinator
requires all three CAN services in a physical profile; the console requires only its profile-aware
`kcan` service.

If setup rejects the checkout, confirm `/opt/e87canbus` is owned by the invoking user and rerun the
role-specific command without `sudo`.

## External validation still required

Repository checks statically verify scripts, units, file ownership, addresses and policy. They do
not validate either installer on a blank Pi, HAT discovery on Pi 4, the physical console CAN mode,
the unused console channel, touchscreen/kiosk behavior, the direct-Ethernet link and isolation, or
either proxy on real hosts. Before vehicle installation also validate CAN polarity, bitrate,
termination, grounding and transceiver compatibility; console Pi plus screen peak demand; and the
HAT power path under reverse battery, cranking and load-dump transients. Avoid simultaneous USB and
HAT power until that path is verified.
