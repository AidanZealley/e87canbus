# Wi-Fi device network

- **Status:** Draft
- **Date:** 2026-08-20

## Goal

Replace the dedicated console Ethernet link with one ignition-switched Wi-Fi network owned by the
coordinator. The console, future cockpit and a service laptop use that network for coordinator
communication. Installed displays continue working without a human login and no vehicle control
loop depends on Wi-Fi.

This is the smallest intended implementation. It does not introduce a general device platform,
remote access or internet connectivity.

## System boundary

```text
                                      K-CAN live vehicle data
                                               |
                                               v
Coordinator Pi  <~~~ private Wi-Fi ~~~>  Console Pi
controller and API                       local UI and K-CAN observer
       ^
       |
       +~~~~~~~~~~~~~~>  ESP32-P4 cockpit
                         config over Wi-Fi, live data from K-CAN
       ^
       |
       +~~~~~~~~~~~~~~>  Service laptop
                         coordinator UI
```

The coordinator remains the only controller owner. Wi-Fi is a UI, configuration and diagnostics
connection. It is not a replacement for the vehicle CAN networks.

## Required behaviour

### Coordinator network

- The coordinator runs one private access point whenever its ignition-switched host is running.
- The access point has no gateway, DNS forwarding or route to another coordinator interface.
- The dedicated `10.43.0.0/30` coordinator-to-console Ethernet network and its proxy are removed.
- Coordinator services listen only where required. SSH remains reachable for service access with
  public-key authentication. Password and root login are disabled. Other unrelated host services
  are not reachable through the Wi-Fi interface.
- The network uses WPA3-SAE with Protected Management Frames required if the coordinator, console
  and selected ESP32-C6 hardware pass a compatibility test. A failed compatibility test must be
  recorded before choosing a weaker mode.
- The Wi-Fi credential is supplied during host and device provisioning. It is not committed to the
  repository or placed in a command line.

### Installed devices

- The console connects without user interaction. The future cockpit must do the same when it
  exists.
- Each installed device has its own signed identity rooted in the installation trust key.
  Possession of the shared Wi-Fi credential does not grant coordinator API access.
- Device credentials identify a fixed role. The first implemented role is `console`. The planned
  `cockpit` role does not require cockpit hardware or firmware in this milestone.
- A device credential authorizes only the coordinator operations needed by that role.
- Installed devices authenticate as devices. They do not display or automate a human login.
- The coordinator accepts a device provisioned later with the installation key without requiring
  prior registration.

The console role may use the HTTP operations and live subscriptions required by the existing
console UI. The cockpit role may read its semantic configuration and, if implemented, report
bounded health. It cannot submit vehicle commands or edit coordinator settings.

### Operator access

- A laptop joins the access point with the normal Wi-Fi password.
- The coordinator web UI requires one operator login before it exposes application state or accepts
  commands and settings changes.
- The first implementation has one locally configured operator identity. User registration,
  password recovery, multiple accounts and remote identity providers are out of scope.
- The first implementation uses HTTP Basic authentication implemented by the FastAPI application.
  It does not add a separate JavaScript authentication service.
- Changing the operator password does not require reprovisioning installed devices.

### Transport security

- Coordinator HTTP and Socket.IO traffic uses HTTPS.
- Installed devices verify the coordinator identity using provisioned trust material. They do not
  disable certificate verification.
- Device credentials never appear in URLs, logs, generated frontend assets or repository files.
- The coordinator stores the public installation trust key, not the installation signing key or a
  device private key.

The exact TLS trust and device proof mechanisms remain open below. They must meet these behaviours
without introducing an external service.

The provisioning flow and installation identity belong to the separate
[device provisioning specification](device-provisioning.md). Devices receive their credentials
before joining Wi-Fi. The coordinator does not offer an unauthenticated first-connect enrollment
flow.

## Console behaviour

- The console continues to serve its frontend locally and observe K-CAN through its local
  receive-only interface.
- Coordinator HTTP and Socket.IO traffic moves from the fixed Ethernet address to the private
  Wi-Fi connection.
- Loss of Wi-Fi marks coordinator-backed state as disconnected. Local K-CAN status remains
  available.
- A command attempted while disconnected fails at that time. The console does not queue it for
  replay after reconnection.
- The console reconnects and obtains a complete current coordinator snapshot through the existing
  live-state recovery contract.
- Console failure or disconnection does not affect coordinator operation.

## Cockpit behaviour

The cockpit remains a future ESP32-P4 and LVGL device. This network milestone must not require its
hardware or firmware to exist.

When implemented, the cockpit:

- reads capture-backed speed, RPM and other live vehicle values directly from K-CAN;
- reads semantic display configuration from the coordinator over Wi-Fi;
- stores the last complete validated configuration locally and uses it immediately at startup;
- replaces its active configuration only after validating a complete response;
- continues to display native K-CAN data when Wi-Fi or the coordinator is unavailable; and
- owns presentation decisions, not vehicle-control decisions.

The initial semantic configuration contains only values required by the first cockpit UI. Layout,
fonts, colours and animations remain firmware-owned until a concrete requirement says otherwise.
The implementation must not add CAN or ISO-TP cockpit configuration alongside Wi-Fi.

## Security and failure limits

- Starting the car makes the network available. It does not replace device or operator
  authentication.
- Wi-Fi loss, interference or authentication failure cannot stop or alter coordinator control.
- The coordinator rejects a credential from another installation or a device attempting an
  operation outside its signed role.
- The console and cockpit expose connection loss rather than displaying stale coordinator state as
  current.
- A compromised cockpit credential cannot authorize console operations. A compromised console
  credential cannot authorize operator-only administration.
- The first implementation cannot revoke one valid device credential. Replacing installation trust
  is the recovery path until denylist or rotation behaviour is specified.
- No part of this work enables internet access, cloud communication, remote vehicle access or
  wireless CAN bridging.

## First implementation milestone

Implement only what is needed to move the existing console:

1. Make the coordinator access point start with the physical coordinator deployment and remain up
   for that ignition-switched boot.
2. Connect the console to that access point using its provisioned network configuration.
3. Add HTTPS, the single operator login and one provisioned `console` device identity.
4. Authenticate the existing console HTTP and Socket.IO traffic without exposing its credential to
   another network client.
5. Remove the console Ethernet configuration, proxy units, deployment checks and documentation.
6. Verify normal startup, reconnection, rejected credentials, command behaviour during disconnect
   and continued coordinator operation while the console is offline.

Do not add the cockpit API, cockpit firmware, credential revocation or rotation, a generic
credential management UI, over-the-air updates or network telemetry during this milestone.

## Acceptance criteria

- A freshly provisioned coordinator starts the private access point without a panel button press.
- A freshly provisioned console joins it automatically and reaches all existing console features
  without a login prompt.
- Disconnecting Ethernet does not change console behaviour because no runtime path uses it.
- A laptop with only the Wi-Fi password cannot read coordinator application data.
- A valid operator login can use the coordinator UI.
- A valid console credential cannot use an operator-only endpoint.
- An invalid console credential or one from another installation cannot establish HTTP or
  Socket.IO access.
- Removing Wi-Fi while the system is running leaves the coordinator ready and makes the console
  visibly disconnected. No failed command runs when Wi-Fi returns.
- Hotspot clients cannot reach another coordinator network or an unrelated host service. SSH is
  the explicit exception and rejects password and root login.
- No secret is present in the repository, process command line, generated frontend bundle or
  application logs.
- Deployment and architecture documentation describe Wi-Fi as the only coordinator-to-console
  network after the cutover.

## Open decisions

These choices need answers before implementation starts:

1. The signed device credential format and proof-of-possession protocol. Credential creation and
   installation are defined by the [device provisioning specification](device-provisioning.md).
2. How the console supplies its credential to both HTTP and Socket.IO without placing it in the
   frontend build.
3. How the local HTTPS certificate is issued and trusted by the console and service laptops.
4. The exact console route and event permissions. Derive these from current console use rather
   than granting the whole coordinator API.

## Documentation impact

Once accepted and implemented, this specification supersedes the Ethernet transport decision in
[ADR 0011](../decisions/0011-separate-coordinator-and-console-hosts.md), changes the hotspot policy
in [ADR 0010](../decisions/0010-constrain-hotspot-ui-exposure.md), and replaces the cockpit CAN
configuration transport proposed in
[ADR 0012](../decisions/0012-kcan-cockpit-display.md). Record those changes in new ADRs rather than
rewriting accepted history.
