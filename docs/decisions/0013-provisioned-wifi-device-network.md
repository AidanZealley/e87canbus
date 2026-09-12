# ADR 0013: Provisioned authenticated Wi-Fi device network

- **Status:** Accepted
- **Date:** 2026-09-12
- **Supersedes:** ADR 0009's hotspot mechanism and button handling, ADR 0010's hotspot exposure,
  ADR 0011's coordinator-console Ethernet link, and ADR 0012's proposed cockpit CAN configuration
  transport. ADR 0009's isolation of panel status from controller work remains in force.

## Context

The coordinator and console need one installation path and one authenticated application network.
The former manual hotspot and direct Ethernet setup depended on a repository checkout, exposed
plain HTTP through two runtime proxies, and did not provide device identity. It also made the
panel responsible for enabling a network the console requires at boot.

## Decision

Provisioning creates one WPA3-SAE network per installation. The coordinator starts it automatically
at `10.42.0.1/24`; the console joins at `10.42.0.2/24`. A bounded DHCP range serves maintenance
laptops without DNS, a default gateway or forwarding.

Nginx exposes the loopback coordinator application at `https://10.42.0.1`. It validates the
installation CA and passes verified console identity to the application. Chromium keeps the
console private key in its local profile and automatically selects it only for the coordinator.
Operators use HTTPS Basic authentication with a separate password. SSH uses the separately
provisioned management key.

The reusable images and one-time consumer replace checkout-based Pi installers. The dedicated
Ethernet network and both plain-HTTP proxy pairs are removed. Wi-Fi carries console UI,
configuration and diagnostics only. The cockpit remains deferred, and this decision does not
select a replacement configuration transport for it.

The coordinator panel is status-only. It reports `STARTING`, `READY`, `FAULT` and `OFF`, and has no
host, simulator or firmware command that can change the provisioned network. The physical button
remains wired and debounced but emits no UART event.

## Consequences

- The console connects without Ethernet, a login prompt or a manual panel action.
- The healthy panel remains at `READY`; pressing its button does not interrupt the console.
- Possessing only the Wi-Fi password grants liveness, not application or SSH access.
- Console or Wi-Fi loss does not affect coordinator control. Disconnected commands fail without
  queuing and reconnection obtains a complete current snapshot.
- Credential compromise requires creating a new installation and reprovisioning both Pis.
- The cockpit remains deferred. This decision does not add a cockpit role or protocol.
