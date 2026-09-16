# Provision coordinator and console Raspberry Pis

This is the only supported blank-card deployment path for the coordinator and console. It builds
reusable Raspberry Pi 4 images, writes one installation recovery package, and provisions each card
with a role-specific application and identity. The Pis do not clone this repository or build
software during first boot.

## Prepare the workstation

Use an arm64 Mac with Docker Desktop, `jq`, two blank SD cards, and a third disposable card for
the failure check. Keep the recovery package outside the repository and back it up in a password
manager or equivalent secret store.

```bash
git status --short
uv sync --locked
uv run e87ctl installation create --output /secure/path/e87canbus-installation-v1.json
uv run e87ctl image build coordinator
uv run e87ctl image build console
```

The installation command also writes a public `-ca.pem` sidecar for a service laptop. The JSON
recovery package contains the installation authority, Wi-Fi and operator credentials, and the
key-only SSH maintenance identity. An ordinary Pi or card failure that remains under your control
needs only a replacement card for that role, provisioned from the same recovery package. Create a
new installation and reprovision both Pis if the recovery package has no backup or if the package,
a Pi, a card or the SSH key may have left your control.

## Provision the pair

Run each command with its role's blank card inserted. Interactive mode lists compatible images and
eligible disks, asks for `car` or `bench`, and prints the exact destructive target before writing.

```bash
uv run e87ctl provision coordinator \
  --installation /secure/path/e87canbus-installation-v1.json
uv run e87ctl provision console \
  --installation /secure/path/e87canbus-installation-v1.json
```

Keep the printed image, application and provisioning digests. `Prepared` and `First boot: pending`
prove only that the card was written and read back. They do not prove that the Pi booted.

Fit the coordinator card to the headless Pi 4 with its three fixed CAN controllers and panel. Fit
the console card to the Pi 4 with its single connected K-CAN controller, display and touchscreen.
Ethernet stays disconnected. Power the coordinator first, then the console.

On the coordinator panel, confirm that the display settles at `READY`. The panel is status-only;
the former network-control button and its host, simulator and firmware paths no longer exist.

Import the public CA sidecar on a service laptop, open `https://e87.local`, and sign in as
`operator` with the password in the recovery package. A laptop with only the Wi-Fi password may
use `/health/live` but cannot read application state. SSH is available as `e87-admin` with the
management private key in the recovery package. Password and root login are disabled. The first
connection accepts the Pi's host key on trust and records it in `known_hosts`, as with any new
host on this isolated, physically controlled network.

Confirm that the console dashboard displays current coordinator-backed state without a prompt or
login. Disconnect the console Wi-Fi and confirm that it reports the coordinator state as
disconnected and rejects an attempted command. Reconnect Wi-Fi and confirm that the dashboard
receives fresh current state without replaying the rejected command. This console check and the
authenticated maintenance session at `https://e87.local` provide the image runbook's end-to-end
TLS evidence.

## First-boot failure

If a Pi never reaches the network, power it down and return its card to the Mac. Mount only its
`BOOT` partition and read the non-secret status:

```bash
(
  set -euo pipefail
  E87_STATUS=/Volumes/BOOT/e87canbus-status-v1.json
  test "$(stat -f %z "$E87_STATUS")" -le 65536
  jq . "$E87_STATUS"
)
```

The strict first-boot consumer writes exactly these nine fields, so its status contract contains no
secret. Compare the printed role, installation ID, device ID and hostname with the expected card.
A failed result and its bounded `error_code` identify the phase to troubleshoot. An identical copy
remains on the root filesystem at `/var/lib/e87canbus-provisioning/status.json` for local
maintenance.

For release acceptance, provision the separate disposable card and add the test-only local debug
shell through the guarded procedure in the image runbook. Set `E87_INVALID_DISK` to the card's
confirmed whole-disk identifier. Corrupt only its provisioning ZIP with this fail-fast command:

```bash
(
  set -euo pipefail
  E87_INVALID_DISK_ID=${E87_INVALID_DISK#/dev/}
  [[ "$E87_INVALID_DISK_ID" =~ ^disk[0-9]+$ ]]
  E87_INVALID_PARTITION="/dev/${E87_INVALID_DISK_ID}s1"
  diskutil info -plist "/dev/$E87_INVALID_DISK_ID" |
    plutil -extract WholeDisk raw - | grep -qx true
  diskutil info -plist "$E87_INVALID_PARTITION" |
    plutil -extract ParentWholeDisk raw - | grep -qx "$E87_INVALID_DISK_ID"
  diskutil info -plist "$E87_INVALID_PARTITION" |
    plutil -extract VolumeName raw - | grep -qx BOOT
  trap 'diskutil unmountDisk "/dev/$E87_INVALID_DISK_ID" >/dev/null 2>&1 || true' EXIT
  diskutil mount "$E87_INVALID_PARTITION"
  diskutil info -plist "$E87_INVALID_PARTITION" |
    plutil -extract MountPoint raw - | grep -qx /Volumes/BOOT
  printf 'invalid provisioning fixture\n' > /Volumes/BOOT/e87canbus-provisioning-v1.zip
  sync
  diskutil unmountDisk "/dev/$E87_INVALID_DISK_ID"
  trap - EXIT
)
```

Set `E87_INVALID_ROLE` to `coordinator` or `console`, boot that role once, and run these checks on
its local debug shell:

```bash
test -e /var/lib/e87canbus-provisioning/unprovisioned
test "$(systemctl show -p ActiveEnterTimestampMonotonic --value e87canbus-role.target)" = 0
case "$E87_INVALID_ROLE" in
  coordinator) E87_INVALID_SERVICE=e87canbus-controller.service ;;
  console) E87_INVALID_SERVICE=e87canbus-console.service ;;
  *) exit 2 ;;
esac
test "$(systemctl show -p ActiveEnterTimestampMonotonic --value "$E87_INVALID_SERVICE")" = 0
```

Remove the temporary checker and debug-shell boot argument as described in the image runbook, then
power down the Pi. Return the card to the Mac and mount only its `BOOT` partition. Record the
bounded failure status, using the card's role:

```bash
(
  set -euo pipefail
  E87_STATUS=/Volumes/BOOT/e87canbus-status-v1.json
  test "$(stat -f %z "$E87_STATUS")" -le 65536
  jq -e '.result == "failed" and .error_code == "invalid_bundle"' "$E87_STATUS"
  jq . "$E87_STATUS"
)
```

The status must report the safe `invalid_bundle` error and the expected role. Because the corrupt
bundle cannot supply trusted identity, it must use an installation ID of 52 `a` characters,
device ID `00000000-0000-4000-8000-000000000000` and hostname
`unprovisioned`. The strict consumer contract keeps the status secret-free. The device must retain
`unprovisioned`, and both activation timestamps above must remain zero. Reprovision the disposable
card before any later use.

## Network and failure behavior

The coordinator owns `10.42.0.1/24` and the console owns `10.42.0.2/24` on one WPA2-Personal
RSN/CCMP network with required management-frame protection. Laptop DHCP is limited to
`10.42.0.100-150` and advertises neither DNS nor a default gateway. Forwarding is disabled and the
firewall accepts
only DHCP, IPv4 mDNS discovery for `e87.local`, HTTPS, key-only SSH and ICMP. The AP deliberately
has no internet route, so macOS's no-internet indicator is expected.

The coordinator remains the only controller owner. Turning off the console or removing Wi-Fi must
leave it ready. The console keeps local K-CAN status, marks coordinator-backed state disconnected,
fails commands attempted while disconnected, and obtains a complete fresh snapshot after
reconnection. It must not replay a failed command.

For image contents and the temporary physical-check helper, see [the image runbook](../images/README.md).
Hardware wiring remains in [the wiring guide](../docs/wiring.md).
