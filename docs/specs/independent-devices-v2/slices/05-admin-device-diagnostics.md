# Slice 05: admin device diagnostics

- **Status:** Draft for approval
- **Depends on:** [Slice 02](02-simulated-button-pad.md) and
  [Slice 04](04-networked-button-pad-cutover.md)

## Outcome

The coordinator admin application shows one generic device list. It separates current access-point
association from the last status a device reported. The driving console contains no device
diagnostics.

## Known devices

`GET /api/devices` returns device IDs and roles already known through authenticated configuration or
status requests. It does not scan for identities and does not create an `e87ctl` inventory.

Each row may include its published and applied configuration generations, last reported status and
coordinator receipt time. Adding a role changes the role-specific status union, not the list layout.

## Network association

At request time, a host adapter reads the access point's current `wpa_supplicant` association data.
It joins associated station MAC addresses to current dnsmasq leases, then matches the exact
certificate-derived hostname `e87-<role>-<device-id>` to a known device row.

Only current association makes `on_wifi` true. No current association makes it false. If the host
cannot read association state, it is `null`. A lease or ARP entry without association does not make
a device online. The hostname and lease perform diagnostic correlation only; neither grants
identity or authority. An associated station that cannot be matched does not impersonate a known
device.

Failure to read association data returns the device records with network diagnostics unavailable.
It does not fail configuration, commands or vehicle behavior.

## Admin UI

The admin application fetches the endpoint as ordinary server state. It shows:

- role and device ID;
- `On Wi-Fi`, `Not on Wi-Fi` or `Unavailable`;
- IP address and hostname when the current lease supplies them;
- published and applied configuration generations; and
- last reported status with its receipt time.

The page fetches on entry and through explicit refresh. It does not create an SSE topic, heartbeat
or background presence poll. Copy must not equate Wi-Fi association with healthy firmware.

## Outside this slice

This slice does not assign configuration to a particular device, rotate credentials, revoke one
device or expose diagnostics in the driving console.

## Acceptance

The slice is complete when:

- only an operator can read the device list;
- known devices appear without a fixed role-specific UI component;
- an associated device with a matching current lease reports `on_wifi` true;
- a stale lease without association reports false;
- adapter failure reports `on_wifi` as `null` rather than stale online or offline data;
- status is labelled and stored as last reported with no expiry;
- opening and manually refreshing the admin page re-reads association data;
- no timer, heartbeat or device SSE connection determines presence; and
- diagnostics never gate configuration, commands or control behavior.
