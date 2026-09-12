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

Join the generated Wi-Fi network from the Mac. Set the two fingerprint variables to the complete
`SHA256:` values recorded from the matching physical Pis, then run both online checks:

```bash
uv run e87ctl verify coordinator \
  --installation /secure/path/e87canbus-installation-v1.json \
  --host-key-fingerprint "$E87_COORDINATOR_SSH_FINGERPRINT"
uv run e87ctl verify console \
  --installation /secure/path/e87canbus-installation-v1.json \
  --host-key-fingerprint "$E87_CONSOLE_SSH_FINGERPRINT"
```

The commands scan the fixed role address and accept SSH only when its Ed25519 host key matches the
explicit fingerprint. They fail if authenticated SSH, provisioning state, installed identity,
release, role services, Wi-Fi, trusted HTTPS readiness or an authorization check fails or is
unavailable. Console verification uses the installed Chromium identity to prove HTTP and
Socket.IO mutual TLS and rejection by the operator-only provisioning endpoint. `--json` returns
the same checks as a versioned document.

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

For release acceptance, provision the separate disposable card, remount its `BOOT` partition,
replace `e87canbus-provisioning-v1.zip` with invalid bytes, unmount it, and boot the matching Pi.
The Pi must keep `unprovisioned`, start no role services, and write a bounded failure status to
`BOOT`. Never reuse that card as one of the successful pair without provisioning it again.

## Network and failure behavior

The coordinator owns `10.42.0.1/24` and the console owns `10.42.0.2/24` on one WPA3-SAE network
with required management-frame protection. Laptop DHCP is limited to `10.42.0.100-150` and
advertises neither DNS nor a default gateway. Forwarding is disabled and the firewall accepts
only DHCP, HTTPS, key-only SSH and normal local-network traffic.

The coordinator remains the only controller owner. Turning off the console or removing Wi-Fi must
leave it ready. The console keeps local K-CAN status, marks coordinator-backed state disconnected,
fails commands attempted while disconnected, and obtains a complete fresh snapshot after
reconnection. It must not replay a failed command.

For image contents and the temporary physical-check helper, see [the image runbook](../images/README.md).
Hardware wiring remains in [the wiring guide](../docs/wiring.md).
