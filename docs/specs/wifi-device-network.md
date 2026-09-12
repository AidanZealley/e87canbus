# Wi-Fi device network

- **Status:** Approved supporting contract
- **Date:** 2026-09-10

## Goal

Replace the dedicated console Ethernet link with one ignition-switched Wi-Fi network owned by the
coordinator. A provisioned console joins without user input and reaches the coordinator through
authenticated HTTPS. A service laptop can join for operator access.

Wi-Fi carries UI, configuration and diagnostics traffic. No vehicle control loop depends on it,
and the network has no internet or forwarding path.

This specification covers only the current coordinator and console. The planned cockpit does not
shape the first implementation.

## System boundary

```text
                                      K-CAN live vehicle data
                                               |
                                               v
Coordinator Pi  <~~~ private Wi-Fi ~~~>  Console Pi
controller, HTTPS API and AP             local UI and K-CAN observer
       ^
       |
       +~~~~~~~~~~~~~~>  Service laptop
                         operator UI and SSH maintenance
```

The coordinator remains the only controller owner. Console or Wi-Fi failure cannot stop or alter
coordinator operation.

## Network behavior

The coordinator starts one private access point whenever its ignition-switched host is running.
Provisioning assigns:

- SSID `e87canbus-<installation-id-prefix>`;
- a generated Wi-Fi password;
- coordinator address `10.42.0.1/24`;
- static console address `10.42.0.2/24`; and
- service-laptop DHCP range `10.42.0.100` through `10.42.0.150`.

NetworkManager owns both Wi-Fi connections and their manual IPv4 configuration. Do not use
NetworkManager shared mode. One minimal `dnsmasq` instance bound to the coordinator hotspot
interface supplies service-laptop addresses with DNS disabled and without advertising a default
gateway or DNS server. The statically configured console does not depend on DHCP.

IP forwarding is disabled. The host firewall drops forwarded traffic and permits hotspot ingress
only for DHCP, HTTPS and key-only SSH plus traffic required for normal local network operation.
Unrelated host services do not listen on or accept traffic from the Wi-Fi interface.

The existing `10.43.0.0/30` coordinator-to-console Ethernet profiles, application proxy units,
checks and documentation are removed. Ethernet is not a fallback transport after cutover.

The coordinator panel reports only coordinator lifecycle state. Its physical button does not start,
stop or otherwise control the provisioned network. NetworkManager autoconnect is the sole runtime
owner of access-point activation.

## Wi-Fi security

The initial configuration uses WPA3-SAE with Protected Management Frames required. NetworkManager
stores the generated password in a root-owned connection profile. It is never committed, passed as
a process argument or written to logs.

The rebuilt coordinator and console images must pass a physical compatibility checkpoint using the
selected Pi Wi-Fi hardware. If either Pi cannot connect reliably with WPA3-SAE and required
management-frame protection, record the evidence and make one explicit fallback decision. Do not
implement several selectable Wi-Fi security modes in advance.

Possession of the Wi-Fi password grants network access only. It grants neither application access
nor Linux login.

## Installation trust and certificates

The [device lifecycle specification](device-provisioning.md) creates one ECDSA P-256 X.509
certificate authority for the installation.

Provisioning gives the coordinator:

- the public installation CA certificate;
- a private server key; and
- a CA-signed server certificate valid for `10.42.0.1` and its provisioned hostname.

Provisioning gives the console:

- the public installation CA certificate;
- a private client key; and
- a CA-signed client certificate containing its installation ID, `console` role and device ID.

The coordinator does not store the installation CA private key or the console private key. The
console does not store the installation CA private key or coordinator private key.

TLS server verification proves coordinator identity to the console. Mutual TLS proves that the
console possesses the private key for a valid client certificate. Do not add bearer tokens, JWTs,
request signatures or another proof protocol.

## HTTPS boundary

The coordinator application continues to bind only to loopback. An OS-packaged nginx instance owns
the external HTTPS listener, verifies certificates against the installation CA and proxies HTTP
and WebSocket traffic to the loopback application.

Nginx requests but does not require a client certificate at the common HTTPS listener. This allows
both access modes:

- a verified console certificate selects device authentication; and
- a client without a device certificate must use operator HTTP Basic authentication.

Nginx replaces all forwarded identity headers rather than accepting client-supplied values. The
FastAPI application trusts them only on its loopback connection from nginx. A failed or untrusted
client certificate cannot reach the application as a device.

Use modern system TLS defaults with TLS 1.2 as the minimum. Do not create a project-specific TLS
implementation or configurable cipher-suite policy.

## Console certificate handling

The console frontend remains locally served by `e87canbus-console`. It sends coordinator HTTP and
Socket.IO traffic directly to `https://10.42.0.1`.

Provisioning imports the console client key and certificate into the `e87-kiosk` Chromium profile
and installs a policy that automatically selects that certificate only for the coordinator HTTPS
origin. It also installs the public installation CA certificate for server verification.

Chromium performs the TLS handshake. Frontend JavaScript cannot read the private key and contains
no credential, password or generated secret. The kiosk must connect without a certificate chooser
or login prompt.

This path requires a physical checkpoint on the rebuilt console image. If unattended certificate
selection is unreliable, stop and replace it with one local console gateway design. Do not build
both paths.

## Operator access

A service laptop joins with the Wi-Fi password and imports the public installation CA certificate
to trust the coordinator HTTPS identity. `e87ctl installation create` writes that public certificate
beside the recovery package. The operator then signs in with the fixed username `operator` and the
generated password stored in the recovery package.

FastAPI implements HTTP Basic authentication. HTTPS protects the credential in transit. The
coordinator stores only an Argon2id password hash. Changing the operator password is outside this
milestone but will not require new device certificates when added.

SSH uses the separate `e87-admin` key from the recovery package. Password and root login are
disabled.

## Authorization

Authentication establishes one of three request classes:

- unauthenticated network client;
- provisioned `console` device; or
- operator.

The authorization layer denies requests unless the route or Socket.IO action explicitly permits
that class.

Unauthenticated clients may use only the external liveness check. It returns process availability,
not application state, configuration or identity details.

The `console` role may use these current production HTTP operations required by the shipped console
UI:

| Methods | Path |
|---|---|
| `GET` | `/health/ready`, `/api/runtime` |
| `GET`, `PUT` | `/api/settings` |
| `PUT` | `/api/steering/maximum-assistance`, `/api/steering/mode` |
| `POST` | `/api/steering/manual-assistance-adjustment`, `/api/steering/activate-profile` |
| `PUT` | `/api/steering/manual-assistance-level`, `/api/steering/curve` |
| `GET`, `POST` | `/api/steering/profiles` |
| `GET` | `/api/steering/profile` |
| `GET`, `PUT`, `DELETE` | `/api/steering/profiles/{profile_id}` |
| `GET`, `POST` | `/api/button-pad/profiles` |
| `GET` | `/api/button-pad/profile` |
| `GET`, `PUT`, `DELETE` | `/api/button-pad/profiles/{profile_id}` |

The console may connect to Socket.IO, send `controller.resync`, `trace.subscribe` and
`trace.unsubscribe`, and receive `controller.snapshot`, `vehicle.state`, `engine.state`,
`steering.state`, `buttons.state`, `lighting.state`, `devices.state`, `controller.health`,
`resources.changed` and `trace.batch`.

This is a closed allowlist derived from the current console client. New API routes or events do not
become console-accessible automatically. Simulator-only operations and installation administration
are never granted to the console role.

The operator may use all production application routes and the operator-only
`GET /api/system/provisioning` endpoint. The console certificate must be rejected by that endpoint.
The executable route-to-permission table lives next to the API routes and has focused tests. Nginx
authenticates certificates but does not duplicate application authorization.

Socket.IO establishes identity during the initial authenticated connection and retains it for that
connection. Reconnection performs authentication again. A failed connection does not leave a
usable session.

## Console behavior

The console continues to serve its frontend locally and observe K-CAN through its local
receive-only interface.

Loss of Wi-Fi marks coordinator-backed state as disconnected. Local K-CAN status remains
available. A command attempted while disconnected fails at that time and is not queued for replay.

After reconnection and mutual-TLS authentication, the console obtains a complete current
coordinator snapshot through the existing live-state recovery contract. Console failure or
disconnection does not affect coordinator operation.

## First implementation flow

Provisioning and network cutover ship as one coordinator-to-console result:

1. A freshly provisioned coordinator starts the access point and HTTPS boundary.
2. A freshly provisioned console joins the access point.
3. Chromium verifies the coordinator and supplies the console client certificate automatically.
4. Nginx verifies the certificate and passes its signed identity to the loopback application.
5. FastAPI applies the `console` allowlist to HTTP and Socket.IO traffic.
6. A service laptop without a client certificate uses operator authentication.
7. The old Ethernet transport and proxies are absent.

## Failure and compromise limits

- Wi-Fi loss, interference or authentication failure cannot stop coordinator control.
- A client from another installation fails certificate verification.
- A certificate with another role receives no console permissions.
- A copied console certificate is insufficient without its private key.
- A compromised console identity can perform the current console operations, including the
  settings and commands exposed by that UI. It cannot use operator-only or simulator operations.
- A client with only the Wi-Fi password cannot read application state.
- The console exposes disconnection rather than presenting coordinator state as current.
- The first implementation cannot revoke one device. Suspected compromise requires a new
  installation and reprovisioning of both Pis.
- No part of this work enables internet access, cloud communication, remote vehicle access or
  wireless CAN bridging.

## Acceptance criteria

- The coordinator access point starts without a panel button press.
- Pressing the coordinator panel button does not change the access point or console connection.
- The console joins automatically and reaches all current console features without a human login.
- WPA3-SAE and required management-frame protection pass on both Pi Wi-Fi devices, or one approved
  evidence-backed fallback replaces them.
- The hotspot advertises no gateway or DNS server and forwards no traffic.
- Disconnecting Ethernet does not change behavior because no runtime path uses it.
- The console verifies the coordinator certificate for `10.42.0.1`.
- Chromium selects the console certificate without exposing its private key to frontend code.
- Invalid, wrong-installation and wrong-role certificates cannot establish console access.
- A laptop with only the Wi-Fi password can read liveness but no application data.
- A valid operator login can use the coordinator UI and provisioning-status endpoint.
- A valid console certificate cannot use the operator-only provisioning-status endpoint.
- Removing Wi-Fi leaves the coordinator ready and makes the console visibly disconnected.
- No command attempted while disconnected runs after reconnection.
- Hotspot clients cannot reach another coordinator network or unrelated host service.
- SSH is the only non-HTTPS service exception and accepts only the provisioned key.
- No secret appears in the repository, process command line, generated frontend bundle or logs.
- Documentation describes Wi-Fi as the only coordinator-to-console network after cutover.

## Deferred work

- Cockpit identity, API and firmware.
- Credential revocation, rotation and renewal.
- Multiple operator accounts and password recovery.
- A network or credential management UI.
- Internet routing, remote access and network telemetry.

## Documentation impact

Once implemented, this specification supersedes the Ethernet transport decision in
[ADR 0011](../decisions/0011-separate-coordinator-and-console-hosts.md), changes the hotspot policy
in [ADR 0010](../decisions/0010-constrain-hotspot-ui-exposure.md), and replaces the cockpit CAN
configuration transport proposed in
[ADR 0012](../decisions/0012-kcan-cockpit-display.md). Record those changes in new ADRs rather than
rewriting accepted history.
