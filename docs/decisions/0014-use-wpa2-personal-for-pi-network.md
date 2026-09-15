# ADR 0014: Use WPA2-Personal for the Pi network

- **Status:** Accepted
- **Date:** 2026-09-14
- **Supersedes:** Only ADR 0013's choice of WPA3-SAE. ADR 0013's network ownership,
  addressing, transport, authorization and panel decisions remain in force.

## Context

The provisioned-pair gate tested both available NetworkManager backends on the target Raspberry Pi
4 stack. The iwd backend rejected SAE access-point profiles. NetworkManager with wpa_supplicant
accepted the profile but could not initialize the SAE access point, reporting `Could not generate
WPA IE`, `WPA initialization failed` and `Failed to initialize AP interface`. Power was healthy at
`get_throttled=0x0`.

We initially considered disabling Protected Management Frames as part of the fallback. The physical
evidence isolates SAE and does not justify that additional downgrade.

## Decision

Use one WPA2-Personal profile with RSN only, CCMP only and Protected Management Frames required.
The NetworkManager keyfile values are `key-mgmt=wpa-psk`, `proto=rsn`, `pairwise=ccmp`,
`group=ccmp` and `pmf=3`.

NetworkManager remains the sole network owner and uses wpa_supplicant as its sole backend.
Provisioning uses the existing generated 32-character random installation password. There is no
selectable security mode, WPA compatibility mode, TKIP path or hostapd service.

## Consequences

- The target hardware can use the approved Wi-Fi network without weakening management-frame
  protection.
- The network loses SAE forward secrecy and resistance to offline password guessing. The random
  32-character installation password makes guessing impractical.
- TLS server verification, mutual TLS device authentication, operator authentication, key-only SSH,
  firewall filtering and disabled forwarding remain unchanged. Possessing the Wi-Fi password still
  grants no application or Linux identity.
- The physical gate must prove both roles activate the exact WPA2-RSN/CCMP profile with `pmf=3`.
