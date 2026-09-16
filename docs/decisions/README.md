# Architecture decisions

These records capture architectural choices that still govern the repository. Hardening plans and
implementation logs are temporary working material; accepted decisions live here after the work is
complete.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-single-owner-event-kernel.md) | Single-owner event kernel | Accepted |
| [0002](0002-capability-controlled-output.md) | Capability-controlled, bounded output | Accepted |
| [0003](0003-production-path-simulation.md) | Production-path simulation with one owner | Accepted |
| [0004](0004-generated-custom-protocol.md) | Generated custom-protocol source of truth | Superseded |
| [0005](0005-atomic-button-led-snapshots.md) | Atomic button-pad LED snapshots | Partially superseded |
| [0006](0006-evidence-gated-hardware-behavior.md) | Evidence-gated hardware behavior | Accepted |
| [0007](0007-servotronic-controller-owns-assistance-mapping.md) | Servotronic-controller-owned assistance mapping | Proposed |
| [0008](0008-unified-controller-architecture.md) | Unified modular controller and transport ownership | Partially superseded |
| [0009](0009-isolate-coordinator-accessories-from-control.md) | Isolated coordinator accessories | Partially superseded |
| [0010](0010-constrain-hotspot-ui-exposure.md) | Constrained hotspot UI exposure | Superseded |
| [0011](0011-separate-coordinator-and-console-hosts.md) | Separate coordinator and console hosts | Partially superseded |
| [0012](0012-kcan-cockpit-display.md) | K-CAN cockpit display with coordinator-owned configuration | Proposed, transport superseded |
| [0013](0013-provisioned-wifi-device-network.md) | Provisioned authenticated Wi-Fi device network | Accepted |
| [0014](0014-use-wpa2-personal-for-pi-network.md) | WPA2-Personal fallback for the Pi network | Accepted |
| [0015](0015-offline-device-provisioning.md) | Offline installation authority and first-boot provisioning | Accepted |
| [0016](0016-advertise-friendly-maintenance-url.md) | Friendly maintenance URL over IPv4 mDNS | Accepted |
| [0017](0017-independent-devices-over-wifi.md) | Independent devices configured over Wi-Fi | Proposed |

New records should be numbered sequentially and contain `Status`, `Context`, `Decision`, and
`Consequences` sections. Supersede an accepted record with a new ADR instead of rewriting the old
decision.
