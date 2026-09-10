# Raspberry Pi host images

This repository builds the validated v1 Raspberry Pi 4 host-image prototypes for the coordinator
and console. They contain stable operating-system and role setup, but no application, installation
identity, secrets, Wi-Fi credentials or operator account. Copying future installation inputs onto
a card will not provision it. The provisioning feature must add the image-side consumer and unique
host identity behavior, then rebuild both roles with this builder and repeat the relevant hardware
checks. Cards flashed from one prototype artifact share its build-time hostname and are not
deployable hosts.

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
uv run e87ctl image build coordinator
uv run e87ctl image build console
```

Each command prints its image path, manifest path and SHA-256 digest. Outputs are local and ignored
by Git:

```text
artifacts/images/coordinator/e87-coordinator_<date>_<time>Z_<commit>.img
artifacts/images/coordinator/e87-coordinator_<date>_<time>Z_<commit>.json
artifacts/images/console/e87-console_<date>_<time>Z_<commit>.img
artifacts/images/console/e87-console_<date>_<time>Z_<commit>.json
```

For example, `e87-coordinator_2026-08-24_1432Z_b3c3206.img`. A build from a dirty
working tree ends in `<commit>-dirty`; the manifest still records the full commit, dirty state and
image digest.

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
Copy the checkpoint script onto the card and append the debug-shell option to the existing single
line in `cmdline.txt`:

```bash
cmdline=/Volumes/BOOT/cmdline.txt
cp images/e87canbus-image-check /Volumes/BOOT/
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
rm -f /boot/firmware/e87canbus-image-check
! grep -qw systemd.debug_shell=1 /boot/firmware/cmdline.txt
sync
systemctl poweroff
```

Do not treat a card as safe to deploy until the negative `grep` check succeeds. Reflashing the
card from the verified image also removes all test-card changes.

## Checks on both roles

The checkpoint script runs the common checks and the selected role checks in one pass. From the
debug shell, run one of:

```bash
sh /boot/firmware/e87canbus-image-check coordinator
sh /boot/firmware/e87canbus-image-check console
```

It prints `PASS` or `FAIL` for every assertion and exits nonzero if anything fails. The script is
the executable source of checkpoint assertions. It checks that the expected Pi 4 and Trixie arm64
system booted without failed units, SSH accepts public keys only, no operator account or application
was baked into the image, and the unprovisioned marker remains present.

## Coordinator checks

Fit the [three-channel CAN stack](../docs/waveshare-three-channel-stack.md) and coordinator panel
according to the [wiring guide](../docs/wiring.md) before booting. A passing coordinator run confirms
that the panel UART exists and all three CAN interfaces use their intended SPI controllers and bit
rates. It also checks the fixed `10.43.0.1/30` Ethernet profile, inactive password-free hotspot,
four-action hotspot sudo policy, and provisioning gates on the application and proxy sockets.

## Console checks

Fit the 2-CH CAN HAT+, with only its first CAN channel in use, and the intended DSI display and
touchscreen before booting. A passing console run confirms that `kcan` is the only CAN interface,
mapped to `spi1.1` at 100 kbit/s in listen-only mode. It also checks the fixed `10.43.0.2/30`
Ethernet profile, Cage, Chromium, DRM, touchscreen input, and provisioning gates on the application
and kiosk.

## Investigate a failure

The failed assertion names the area to inspect. These commands expose the useful raw state without
duplicating the checker's assertions:

```bash
systemctl --failed --no-legend --plain
systemctl list-units --all 'e87canbus-*' ssh.service avahi-daemon.service --no-pager
systemctl list-unit-files 'e87canbus-*' --no-pager
journalctl -b -u 'e87canbus-*' --no-pager
for interface in kcan ptcan fcan; do
  test -e "/sys/class/net/$interface" || continue
  printf '\n%s -> %s\n' "$interface" "$(readlink -f "/sys/class/net/$interface/device")"
  ip -details link show "$interface"
done
nmcli connection show
for device in /dev/input/event*; do
  test -e "$device" || continue
  udevadm info --query=property --name="$device" | \
    sed -n '/^DEVNAME=/p; /^ID_INPUT/p'
done
```

These commands report services, boot logs, existing CAN interfaces, NetworkManager profiles and
input-device classification on either role. Do not add credentials or enable application units to
make the reusable-image checkpoint pass.

The checkpoint cannot exercise the application health check or launch the kiosk. The future
provisioning work must add the missing image-side consumer before it can install the application,
operator account and unique host identity. The checkpoint also does not prove CAN traffic, hotspot
credentials, paired-host Ethernet reachability or vehicle-safe wiring. Those are installation
acceptance checks, not reusable-image checks.

## Record the checkpoint

For each role, record:

- the build command result, image filename, size and SHA-256 digest;
- Raspberry Pi Imager write and verification result;
- Pi model and OS checks;
- failed-unit output;
- the checkpoint script's complete `PASS` or `FAIL` output; and
- confirmation that `systemd.debug_shell=1` was removed or the card was reflashed.
