# ADR 0010: Constrain hotspot UI exposure

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

The coordinator web application normally listens only on loopback. A laptop connected to the
coordinator's Wi-Fi hotspot needs to reach that application, while the hotspot must not expose the
controller on other interfaces, become an internet-sharing path through Ethernet, or give the
unprivileged controller service general networking authority.

Hotspot credentials must also be provisionable without storing them in the repository, process
environment, or command line.

## Decision

Physical profiles provision one fixed NetworkManager connection and leave it disabled after boot.
A socket-activated proxy binds port 80 only to the hotspot address and forwards requests to the
loopback controller. A dedicated policy-routing blackhole prevents hotspot clients from being
forwarded through an Ethernet default route.

The controller service may invoke a root-owned helper only through exact passwordless sudo rules.
The helper hard-codes the connection and interface and accepts only `activate`, `deactivate`,
`state`, and `stations`; it rejects extra arguments and cannot edit connections or run arbitrary
`nmcli` or `iw` operations.

Setup accepts the WPA credential through a silent interactive prompt or a password file outside the
checkout. It passes the value to NetworkManager without putting it in the repository, command line,
or controller environment. Rerunning setup without a supplied credential preserves the existing
one.

## Consequences

- The application remains loopback-only even though it is reachable from the dedicated hotspot.
- Other host interfaces do not inherit the hotspot's HTTP exposure.
- Compromise of the controller service grants only the four fixed hotspot operations, not general
  privileged networking access.
- The fixed connection, interface, address, and helper actions are deployment policy rather than a
  reusable Wi-Fi management API.
