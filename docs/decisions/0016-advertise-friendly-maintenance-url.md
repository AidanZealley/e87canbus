# ADR 0016: Advertise a friendly maintenance URL with IPv4 mDNS

- **Status:** Accepted
- **Date:** 2026-09-16

## Context

A maintenance laptop can reach the coordinator by its fixed IP address, but the address is awkward
to recall and the isolated AP deliberately supplies neither DNS nor an internet route. There is no
active advertisement for a stable friendly name.

## Decision

The coordinator advertises the bare `e87.local` host name through IPv4 mDNS on `wlan0`. Its server
certificate includes `e87.local` alongside `10.42.0.1`, its provisioned hostname and its signed
per-installation device identity. This adds no `_https._tcp` service advertisement or general
discovery framework.

The AP remains isolated: dnsmasq DNS stays disabled, DHCP supplies no router or DNS option, IP
forwarding stays disabled, and the firewall permits only IPv4 mDNS multicast traffic required to
reach Avahi. Possessing only the Wi-Fi password still grants no application or SSH access. The
console continues to use and verify `https://10.42.0.1`; the friendly name is for maintenance
laptops only.

This is a hard cutover for certificate issuance. Existing installed devices remain available by
IP and are not migrated in place. They gain `e87.local` only after generating a fresh provisioning
bundle and reprovisioning with the updated certificate profile.

## Consequences

- Maintenance laptops can open `https://e87.local` after trusting the installation CA.
- macOS still shows its expected no-internet indicator because the AP has no internet route.
- An mDNS collision that renames the effective Avahi host causes verification to fail rather than
  silently publishing a different URL.
- The per-installation CA, signed device identity, operator authentication and console mTLS
  boundaries are unchanged.
