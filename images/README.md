# Raspberry Pi host images

This repository builds reusable Raspberry Pi 4 host images for the coordinator and console. The
images contain stable operating-system and role setup. They do not contain the application,
installation identity, secrets, Wi-Fi credentials or an operator account.

## Build on Apple silicon

Use a clean checkout on an arm64 Mac with Docker Desktop running. The supported and tested host is
the M1 Pro MacBook. The build downloads Debian and Raspberry Pi packages, so it needs network
access. Docker keeps downloaded packages in the named volume `e87canbus-pi-image-packages` between
builds.

Check the source tree before starting. A dirty tree is allowed and recorded in the manifest, but
it is not an acceptable hardware-checkpoint candidate.

```bash
git status --short
docker info >/dev/null
uname -m
```

`uname -m` must print `arm64`. Build each role from the repository root:

```bash
./scripts/build-pi-image coordinator
./scripts/build-pi-image console
```

Each command prints its image path, manifest path and SHA-256 digest. Outputs are local and ignored
by Git:

```text
artifacts/images/coordinator/<build>.img
artifacts/images/coordinator/<build>.json
artifacts/images/console/<build>.img
artifacts/images/console/<build>.json
```

Inspect the newest artifact for a role without assuming a build identifier:

```bash
role=coordinator
manifest=$(ls -t "artifacts/images/${role}"/*.json | head -n 1)
image="${manifest%.json}.img"
cat "$manifest"
expected=$(sed -n 's/.*"sha256": "\([^"]*\)".*/\1/p' "$manifest")
actual=$(shasum -a 256 "$image" | awk '{print $1}')
test "$actual" = "$expected"
printf 'Image: %s\nSHA-256: %s\n' "$image" "$actual"
```

Repeat with `role=console`. Check that the manifest says:

- `git_dirty` is `false` and `git_commit` is the checkpoint commit;
- `architecture` is `arm64`;
- `raspberry_pi_model` is `Raspberry Pi 4 Model B`;
- `os_release` is `Raspberry Pi OS Lite Trixie`; and
- `role` matches the card being tested.

## Write a test card

Open Raspberry Pi Imager and choose **Use Custom**. Select the role's `.img`, select the test SD
card, then write it and wait for Imager verification to finish. Confirm the image path and target
device before writing.

Raspberry Pi Imager did not offer OS customisation for the base checkpoint's custom image. Do not
depend on Imager to create a test user or install an SSH key. The reusable image deliberately has
no operator account, and its SSH server accepts public keys only.

### Temporary local access

Use [systemd's debug shell](https://www.freedesktop.org/software/systemd/man/latest/systemd-debug-generator.html)
for this hardware checkpoint. This changes only the flashed test card. It does not change the
`.img`, its manifest or repository source. It creates no user or credential.

After Imager has verified the card, eject and reinsert it so macOS mounts its `BOOT` partition.
Append the debug-shell option to the existing single line in `cmdline.txt`:

```bash
cmdline=/Volumes/BOOT/cmdline.txt
grep -qw systemd.debug_shell=1 "$cmdline" || \
  perl -0pi -e 's/\s*\z/ systemd.debug_shell=1\n/' "$cmdline"
grep -n systemd.debug_shell=1 "$cmdline"
diskutil eject /Volumes/BOOT
```

The debug shell gives unauthenticated root access on local virtual terminal 9. Keep the Pi away
from untrusted networks and vehicle wiring while it is enabled. Connect the role hardware, HDMI
display and keyboard, then boot. Wait for boot to settle and press Control-Option-F9 on an Apple
keyboard. Hold Fn as well if its top row controls media. On a PC keyboard, press Control-Alt-F9.

Before reusing or handing over the card, remove the debug shell and power off:

```bash
sed -i 's/[[:space:]]systemd\.debug_shell=1//g' /boot/firmware/cmdline.txt
! grep -qw systemd.debug_shell=1 /boot/firmware/cmdline.txt
sync
systemctl poweroff
```

Do not treat a card as safe to deploy until the negative `grep` check succeeds. Reflashing the
card from the verified image also removes all test-card changes.

## Checks on both roles

Run these commands from the debug shell:

```bash
test "$(uname -m)" = aarch64
grep -qx 'VERSION_CODENAME=trixie' /etc/os-release
tr -d '\0' </proc/device-tree/model | grep -q '^Raspberry Pi 4 Model B'
test -z "$(systemctl --failed --no-legend --plain)"
systemctl is-active ssh.service
/usr/sbin/sshd -T | grep -qx 'authenticationmethods publickey'
test -z "$(getent passwd 1000 || true)"
test -e /var/lib/e87canbus-provisioning/unprovisioned
test ! -e /opt/e87canbus/.venv/bin/e87canbus
```

These checks should produce no error. They prove the expected board and OS booted, the image has
no baked-in operator, SSH remains key-only, and the application is still blocked on later
provisioning.

## Coordinator checks

Fit the [three-channel CAN stack](../docs/waveshare-three-channel-stack.md) and coordinator panel
according to the [wiring guide](../docs/wiring.md) before booting. Run:

```bash
test -e /dev/ttyAMA3
systemctl is-active avahi-daemon.service e87canbus-kcan.service \
  e87canbus-ptcan.service e87canbus-fcan.service
readlink -f /sys/class/net/kcan/device | grep -q '/spi0.0/'
readlink -f /sys/class/net/ptcan/device | grep -q '/spi1.1/'
readlink -f /sys/class/net/fcan/device | grep -q '/spi1.2/'
ip -details link show kcan | grep -q 'bitrate 100000'
ip -details link show ptcan | grep -q 'bitrate 500000'
ip -details link show fcan | grep -q 'bitrate 500000'
nmcli -g connection.interface-name,connection.autoconnect,ipv4.addresses,ipv4.never-default \
  connection show e87canbus-console-link
! nmcli -t -f NAME connection show --active | grep -qx e87canbus-hotspot
test -z "$(nmcli --show-secrets -g 802-11-wireless-security.psk \
  connection show e87canbus-hotspot)"
for unit in e87canbus-controller.service \
  e87canbus-coordinator-hotspot-proxy.socket \
  e87canbus-coordinator-console-proxy.socket; do
  test "$(systemctl is-active "$unit")" = inactive
  test "$(systemctl is-enabled "$unit")" = disabled
done
sudo -u e87canbus sudo -n -l
```

The Ethernet profile must report `eth0`, `yes`, `10.43.0.1/30` and `yes`. The sudo listing must
contain only the four exact `e87canbus-hotspot` actions: `activate`, `deactivate`, `state` and
`stations`. The hotspot remains inactive and has no password. The controller and both proxy
sockets remain disabled until provisioning installs the application and installation inputs.

## Console checks

Fit the 2-CH CAN HAT+, with only its first CAN channel in use, and the intended DSI display and
touchscreen before booting. Run:

```bash
systemctl is-active e87canbus-console-kcan.service
can_interfaces=$(for interface in /sys/class/net/*; do
  test "$(cat "$interface/type")" = 280 && basename "$interface"
done)
test "$can_interfaces" = kcan
readlink -f /sys/class/net/kcan/device | grep -q '/spi1.1/'
ip -details link show kcan | grep -q 'bitrate 100000'
ip -details link show kcan | grep -q 'listen-only on'
nmcli -g connection.interface-name,connection.autoconnect,ipv4.addresses,ipv4.never-default \
  connection show e87canbus-console-link
command -v cage chromium
test -n "$(find /dev/dri -maxdepth 1 -name 'card*' -print -quit)"
touchscreen=
for device in /dev/input/event*; do
  test -e "$device" || continue
  if udevadm info --query=property --name="$device" | \
    grep -qx 'ID_INPUT_TOUCHSCREEN=1'; then
    touchscreen=$device
    break
  fi
done
test -n "$touchscreen"
printf 'Touchscreen: %s\n' "$touchscreen"
test "$(systemctl is-active e87canbus-console.service)" = inactive
test "$(systemctl is-active e87canbus-console-kiosk.service)" = inactive
test "$(systemctl is-enabled e87canbus-console.service)" = disabled
test "$(systemctl is-enabled e87canbus-console-kiosk.service)" = disabled
```

The Ethernet profile must report `eth0`, `yes`, `10.43.0.2/30` and `yes`. The image should expose
only `kcan`, mapped to `spi1.1` at 100 kbit/s in listen-only mode. Cage, Chromium, DRM and the
touchscreen input must be present. The application and kiosk must remain inactive and disabled.

The checkpoint cannot exercise the application health check or launch the kiosk. That requires
the application bundle and operator account. The later provisioning CLI supplies both. It also
does not prove CAN traffic, hotspot credentials, paired-host Ethernet reachability or vehicle-safe
wiring. Those are installation acceptance checks, not reusable-image checks.

## Record the checkpoint

For each role, record:

- the build command result, image filename, size and SHA-256 digest;
- Raspberry Pi Imager write and verification result;
- Pi model and OS checks;
- failed-unit output;
- every role-specific command result; and
- confirmation that `systemd.debug_shell=1` was removed or the card was reflashed.
