# ADR 0011: Separate coordinator and console hosts

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

The coordinator previously hosted both vehicle control and the driver-facing screen. Their
physical locations, hardware needs and failure boundaries now differ: control belongs near the
junction box, while the display and touchscreen belong in the dashboard. The console needs a
small local proof that receive-only K-CAN can reach React, but it must not become another control
owner or expose raw CAN.

[ADR 0008](0008-unified-controller-architecture.md) continues to define the coordinator's single
controller owner and authoritative APIs. [ADR 0009](0009-isolate-coordinator-accessories-from-control.md)
keeps optional accessories outside that control path, and
[ADR 0010](0010-constrain-hotspot-ui-exposure.md) establishes interface-bound proxy exposure.

## Decision

Deploy two fixed Raspberry Pi 4 host roles:

- The headless coordinator owns the controller, all CAN transmission capability, durable state,
  diagnostics, coordinator frontend, three CAN interfaces and coordinator panel.
- The console owns its locally hosted driver frontend, kiosk and one receive-only K-CAN interface.
  Its local service publishes only complete, bounded connection/frame-count/fault snapshots. It
  has no controller kernel, durable authority, CAN transmitter or raw-frame browser API.

Both roles install the same `hosts` Python project, while `frontend/apps/coordinator` and
`frontend/apps/console` build independently. UI-free generated coordinator contracts and client
state used by both apps live in `frontend/packages/coordinator-client`.

The hosts communicate over a fixed, point-to-point `10.43.0.0/30` Ethernet link: coordinator
`10.43.0.1`, console `10.43.0.2`, with no gateway, DNS, forwarding or internet sharing. The
coordinator application stays loopback-bound and is exposed to this link only by a proxy bound to
`10.43.0.1:80`. The console application and frontend remain loopback-bound on the console.

## Consequences

- The coordinator continues operating when the console or Ethernet link fails. Local console
  K-CAN observation remains independent when the coordinator is unavailable.
- Host roles are direct deployment compositions, not new controller profiles or a generic role
  framework. The existing `car`, `bench` and `simulator` profiles remain coordinator concerns.
- Console activity is an end-to-end diagnostic proof, not a decoded vehicle feature. Future
  signals still require capture-backed, network-specific evidence and one authoritative owner.
- The console's application receive-only boundary is reinforced by kernel listen-only mode. Its
  unused HAT+ channel has no overlay, interface name or service and remains disconnected.
- Static repository checks can verify configuration and ownership, but blank-Pi installation,
  physical CAN/listen-only behavior, direct Ethernet, display, power and vehicle wiring remain
  pending hardware validation.

This decision extends ADRs 0008-0010 and supersedes no unrelated decision.
