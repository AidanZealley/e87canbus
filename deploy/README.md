# Provision coordinator and console Raspberry Pis

This is the only supported blank-card deployment path for the coordinator and console. It builds
reusable Raspberry Pi 4 images, writes one installation recovery package, and provisions each card
with a role-specific application and identity. The Pis do not clone this repository or build
software during first boot.

## Prepare the workstation

Use an arm64 Mac with Docker Desktop, two blank SD cards, and a third disposable card for the
failure check. Keep the recovery package outside the repository and back it up in a password
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

During physical commissioning, use each Pi's local debug shell to record its trusted host key:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub -E sha256
```

Start the guided pair check before joining the Wi-Fi network. It asks for the recovery-package
path, both recorded `SHA256:` fingerprints and a report path, then tells you when to switch
networks:

```bash
uv run e87ctl verify
```

After you confirm the switch it verifies the coordinator and the console twice each, prints every
check, and saves one secret-free JSON report of all four results and their elapsed times. Bad
local input fails before the network switch, so you keep your internet connection while correcting
it. A device failure exits nonzero and still saves the evidence collected so far, which you can
read once the Mac is back on its normal network. Choose a new report path for each attempt: the
command refuses to overwrite an existing file.

For automation or focused troubleshooting, run a single role directly instead. Set each variable
to the complete `SHA256:` value recorded from its physical Pi:

```bash
uv run e87ctl verify coordinator \
  --installation /secure/path/e87canbus-installation-v1.json \
  --host-key-fingerprint "$E87_COORDINATOR_SSH_FINGERPRINT"
uv run e87ctl verify console \
  --installation /secure/path/e87canbus-installation-v1.json \
  --host-key-fingerprint "$E87_CONSOLE_SSH_FINGERPRINT"
```

Both forms run the same checks. They scan the fixed role address and accept SSH only when its
Ed25519 host key matches the explicit fingerprint. They fail if authenticated SSH, provisioning
state, installed identity, release, role services, Wi-Fi, trusted HTTPS readiness or an
authorization check fails or is unavailable. Console verification uses the installed Chromium
identity to prove HTTP and Socket.IO mutual TLS and rejection by the operator-only provisioning
endpoint. `--json` returns the same checks as a versioned document for a single role.

On the coordinator panel, confirm that the display settles at `READY`. The panel is status-only;
the former network-control button and its host, simulator and firmware paths no longer exist.

Import the public CA sidecar on a service laptop, open `https://10.42.0.1`, and sign in as
`operator` with the password in the recovery package. A laptop with only the Wi-Fi password may
use `/health/live` but cannot read application state. SSH is available as `e87-admin` with the
management private key in the recovery package. Password and root login are disabled.

## First-boot failure

If a Pi never reaches the network, power it down and return its card to the Mac. Mount only its
`BOOT` partition and read the non-secret status:

```bash
uv run e87ctl verify coordinator \
  --installation /secure/path/e87canbus-installation-v1.json \
  --status /Volumes/BOOT/e87canbus-status-v1.json
```

Offline status is diagnostic and therefore always leaves online verification unavailable. The
command exits nonzero even when the status says first boot succeeded.

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
# Use console if that is the disposable card's role.
E87_INVALID_ROLE=coordinator
E87_RECOVERY=/secure/path/e87canbus-installation-v1.json
uv run e87ctl verify "$E87_INVALID_ROLE" \
  --installation "$E87_RECOVERY" \
  --status /Volumes/BOOT/e87canbus-status-v1.json \
  --json
```

The command must exit nonzero, report the safe `invalid_bundle` error, leave online verification
unavailable and contain no secret. The device must retain `unprovisioned`, and both activation
timestamps above must remain zero. Reprovision the disposable card before any later use.

## Network and failure behavior

The coordinator owns `10.42.0.1/24` and the console owns `10.42.0.2/24` on one WPA2-Personal
RSN/CCMP network with required management-frame protection. Laptop DHCP is limited to
`10.42.0.100-150` and advertises neither DNS nor a default gateway. Forwarding is disabled and the
firewall accepts
only DHCP, HTTPS, key-only SSH and normal local-network traffic.

The coordinator remains the only controller owner. Turning off the console or removing Wi-Fi must
leave it ready. The console keeps local K-CAN status, marks coordinator-backed state disconnected,
fails commands attempted while disconnected, and obtains a complete fresh snapshot after
reconnection. It must not replay a failed command.

For image contents and the temporary physical-check helper, see [the image runbook](../images/README.md).
Hardware wiring remains in [the wiring guide](../docs/wiring.md).
