# Candidate `eda0d12` physical gate report

Date: 2026-09-15

Verdict: **Passed for the software and image workflow.**

Both images were built from exact clean commit
`eda0d12cfb56a23ed71bd1a3e33eb40be229b75b` with `git_dirty=false`, written to fresh cards and
provisioned successfully. The display and console Pi were physically separated while remaining
connected by the DSI ribbon. The console associated immediately, remained at `10.42.0.2` and loaded
car settings through the authenticated coordinator API.

## Coordinator

- Artifact: `artifacts/images/coordinator/e87-coordinator_2026-09-15_1158Z_eda0d12.img`
- Image SHA-256: `fb408e49495c1ecec813bbc22749e036b5cc953cad5224af01a8a5f7dbd78960`
- Hostname: `e87-coordinator-61f3fe49402f`
- Device ID: `61f3fe49-402f-4b6a-88c9-aa4c60d73999`
- Application digest: `d800e2909c38769ebdfe4b95daeaed29c288a97043a8aa8b54876a7eccfbcf50`
- Provisioning digest: `2759f6aa2dec422400fdc351c1ddb44a42253ed70d9731959e0aa29a905b4f25`
- SSH ED25519 fingerprint: `SHA256:HxFkqNtyrWaXcux7+gb1CZqdfN2fYPYQZLSYvYYGcOU`
- Provisioning result: `succeeded`

The complete coordinator image checker passed. The authenticated HTTPS listener was active at
`10.42.0.1:443`, no listener was exposed on port 80, the stock nginx unit was masked and the product
nginx unit was `active (running)` with `NRestarts=0`. Controller health and console-originated
`GET /api/settings` requests returned HTTP 200. The WPA2-RSN access point used CCMP,
WPA2-PSK-SHA256 and required PMF. CAN interfaces and rates passed, forwarding remained disabled and
systemd reported no failed units.

## Console

- Artifact: `artifacts/images/console/e87-console_2026-09-15_1205Z_eda0d12.img`
- Image SHA-256: `368bc5e85308b5e3e4ffe11df3e7c4fe1427e0d2efd29278e97e3234414a5797`
- Hostname: `e87-console-a6610795808e`
- Device ID: `a6610795-808e-4781-a4d6-e8969fe5d4c4`
- Application digest: `2cc79f20212d8bf8196ae0dd77d80a6fc5bd0b87fb21f6d7275579d412bb28b8`
- Provisioning digest: `ed10f0fd13510ea74b86220c1fcad58fd98de9ea508533024f531e299ea02fa0`
- SSH ED25519 fingerprint: `SHA256:RKkcuIJs+geJwNrsvSCKoTTH4Hwp/M38P320Nc8Yhzk`
- Provisioning result: `succeeded`

The complete console image checker passed. Association, WPA key negotiation and
`CTRL-EVENT-CONNECTED` completed successfully. WPA2-PSK-SHA256, CCMP and management-frame
protection were active. The Chromium client-certificate database and certificate-selection policy,
console and kiosk services, DRM, touchscreen and bench-profile kcan checks passed. Systemd reported
no failed units.

## Shared installation and runtime

- Installation ID: `jv4xu4p3ip2r6ngwxlbgv3nwpx6wx7yeeufe5kerapegyej44c4q`
- Deployment profile: `bench`
- Kernel on both roles: `6.18.50+rpt-rpi-v8`
- `firmware-brcm80211` on both roles: `1:20260519-1~bpo13+1+rpt1`
- Loaded BCM4345/6 firmware on both roles: `7.45.265`, FWID `01-b677b91b`

Both complete image checkers were streamed over SSH from the exact candidate checkout. No checker
file was copied to or retained on either card. No device configuration was modified to obtain the
result.

## Outcome

The coordinator HTTPS correction in `417d4b47ba7746b8da5472bc364b230a29d0e5eb` is physically
verified. The stock nginx unit is masked, port 80 is absent, the intended HTTPS listener is stable,
Chromium mutual TLS succeeds and the settings API works end to end.

The former status-16 failure is isolated to physical DSI/display proximity interference. A
mechanical spacer still needs design and validation. Aidan classified that as hardware integration
work that does not block completion of the software and image workflow.
