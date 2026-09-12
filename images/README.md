# Raspberry Pi host images

This directory builds the provisionable Raspberry Pi 4 coordinator and console image candidates.
Each image contains the stable OS configuration and one strict first-boot consumer. It contains no
application release, installation credential, operator account or reusable host identity.

The device lifecycle workflow owns acceptance. Automated image checks do not prove Raspberry Pi
radio behavior, Chromium certificate selection or the macOS writer. See
[`docs/specs/device-provisioning/implementation/README.md`](../docs/specs/device-provisioning/implementation/README.md)
for the current gate status and evidence requirements.

## Build on Apple silicon

Use an arm64 Mac with Docker Desktop running. The build downloads Debian and Raspberry Pi packages
and reuses the `e87canbus-pi-image-packages` Docker volume.

```bash
git status --short
docker info >/dev/null
test "$(uname -m)" = arm64
uv run e87ctl image build coordinator
uv run e87ctl image build console
```

Generated images and manifests are ignored by Git under:

```text
artifacts/images/coordinator/
artifacts/images/console/
```

The command prints each image path, manifest path and SHA-256 digest. Check the latest result without
assuming its generated name:

```bash
role=coordinator
manifest=$(ls -t "artifacts/images/${role}"/*.json | head -n 1)
image="${manifest%.json}.img"
expected=$(sed -n 's/.*"sha256": "\([^"]*\)".*/\1/p' "$manifest")
actual=$(shasum -a 256 "$image" | awk '{print $1}')
test "$actual" = "$expected"
cat "$manifest"
```

Repeat with `role=console`. The strict v1 manifest records the role, Pi model, Trixie arm64 OS,
pinned builder revision, Git context, image digest, provisioning interface version and boot/root
storage limits. The FAT boot partition keeps rpi-image-gen's `BOOT` label, which the macOS writer
uses as the exact partition identity.

## Image contents

Both roles:

- remove the builder hostname, `/etc/machine-id` and SSH host keys before publication;
- contain `e87canbus-provision.service` and the protected `unprovisioned` marker;
- contain no application, recovery package, device certificate, network secret or SSH authorized
  key;
- generate the machine ID and SSH host keys locally; and
- keep the role target stopped until the consumer validates, stages, installs and cleans a bundle.

The coordinator image also contains nginx, dnsmasq and nftables. Provisioning supplies the WPA3-SAE
access-point profile and TLS identity. Nginx listens at `10.42.0.1:443`, requests a client
certificate and replaces the two trusted identity headers before proxying to the loopback
application. Dnsmasq offers only `10.42.0.100` through `10.42.0.150`, with no DNS or default
gateway. The firewall drops forwarding and permits hotspot ingress only for DHCP, HTTPS, SSH and
ICMP.

The console image contains Cage, Chromium and NSS tools. Provisioning supplies the static
`10.42.0.2/24` WPA3-SAE profile, imports its client identity into the `e87-kiosk` Chromium profile
and installs automatic certificate selection only for `https://10.42.0.1`.

First boot does not run `apt`, `pip`, `uv`, `npm` or `pnpm`. It installs the ready application under
`/opt/e87canbus/releases/<digest>` and activates `/opt/e87canbus/current` only after complete bundle
validation. Success removes the boot bundle and staged secrets, writes non-secret status to the
root and `BOOT` filesystems, then clears `unprovisioned`. An invalid bundle leaves the marker and
all role services disabled.

## Physical checkpoint

Build both roles from one clean candidate commit. Use the public provisioning commands and follow
the macOS writer gate before booting either Pi:

```bash
uv run e87ctl provision coordinator --installation <recovery-package>
uv run e87ctl provision console --installation <recovery-package>
```

The workflow records the exact image, provisioning and application digests. It also owns the
deliberately invalid-bundle card used to prove offline failure status.

For the successful pair, copy `images/e87canbus-image-check` to the test card's `BOOT` partition
and use a test-only local console such as `systemd.debug_shell=1`. This changes only the flashed
test card. It creates no user or credential. On the Mac, set `E87_TEST_DISK` to the confirmed
whole-disk identifier for that card and prepare the temporary input:

```bash
(
  set -euo pipefail
  E87_TEST_DISK_ID=${E87_TEST_DISK#/dev/}
  [[ "$E87_TEST_DISK_ID" =~ ^disk[0-9]+$ ]]
  E87_TEST_PARTITION="/dev/${E87_TEST_DISK_ID}s1"
  diskutil info -plist "/dev/$E87_TEST_DISK_ID" |
    plutil -extract Whole raw - | grep -qx true
  diskutil info -plist "$E87_TEST_PARTITION" |
    plutil -extract ParentWholeDisk raw - | grep -qx "$E87_TEST_DISK_ID"
  diskutil info -plist "$E87_TEST_PARTITION" |
    plutil -extract VolumeName raw - | grep -qx BOOT
  trap 'diskutil unmountDisk "/dev/$E87_TEST_DISK_ID" >/dev/null 2>&1 || true' EXIT
  diskutil mount "$E87_TEST_PARTITION"
  diskutil info -plist "$E87_TEST_PARTITION" |
    plutil -extract MountPoint raw - | grep -qx /Volumes/BOOT
  cp images/e87canbus-image-check /Volumes/BOOT/
  grep -qw systemd.debug_shell=1 /Volumes/BOOT/cmdline.txt ||
    sed -i '' '1s/$/ systemd.debug_shell=1/' /Volumes/BOOT/cmdline.txt
  sync
  diskutil unmountDisk "/dev/$E87_TEST_DISK_ID"
  trap - EXIT
)
```

Boot the Pi, open the local debug shell on tty9 and run:

```bash
sh /boot/firmware/e87canbus-image-check coordinator
sh /boot/firmware/e87canbus-image-check console
```

The executable is the source of checkpoint assertions. It checks the Raspberry Pi 4 Model B and
Trixie arm64 base, unique host state, successful provisioning status, `BOOT` label, active
release, key-only SSH and role services. Coordinator checks cover the panel UART and three CAN
interfaces. Console checks cover `kcan` in listen-only mode, DRM and touchscreen input. Network
checks cover the `10.42.0.1/24` coordinator access point, `10.42.0.2/24` console client, WPA3/PMF
policy, no forwarding and the console Chromium certificate store.

Remove the temporary debug shell and checker before reusing a card:

```bash
sed -i 's/[[:space:]]systemd\.debug_shell=1//g' /boot/firmware/cmdline.txt
rm -f /boot/firmware/e87canbus-image-check
! grep -qw systemd.debug_shell=1 /boot/firmware/cmdline.txt
sync
systemctl poweroff
```

Do not report the images as accepted until the workflow contains the complete MacBook, Raspberry
Pi Imager, Pi 4, network, TLS and cleanup evidence for the exact candidate.

After both Pis boot, join their Wi-Fi network and run `e87ctl verify coordinator` and `e87ctl
verify console` with the installation recovery package. The [provisioning runbook](../deploy/README.md)
contains the complete pair and invalid-bundle acceptance procedure.
