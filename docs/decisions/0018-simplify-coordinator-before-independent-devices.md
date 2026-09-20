# ADR 0018: Simplify the coordinator before independent devices

- **Status:** Accepted
- **Date:** 2026-09-18
- **Supersedes:** [ADR 0004](0004-generated-custom-protocol.md) and
  [ADR 0005](0005-atomic-button-led-snapshots.md)
- **Partially supersedes:** [ADR 0001](0001-single-owner-event-kernel.md),
  [ADR 0002](0002-capability-controlled-output.md),
  [ADR 0003](0003-production-path-simulation.md),
  [ADR 0008](0008-unified-controller-architecture.md),
  [ADR 0012](0012-kcan-cockpit-display.md) and
  [ADR 0017](0017-browser-live-state-over-sse.md)

## Context

The coordinator directly configured and controlled the button pad and Servotronic controller over a
generated custom CAN protocol. That implementation spread device lifecycle, transport, output
failure and simulation concerns through the kernel, runtimes, live contract and frontend.

Neither device is in use. Preserving those paths while adding independent HTTPS clients would keep
two architectures alive and force the new work to integrate with machinery that has no remaining
product purpose.

The coordinator also contains a high-beam flash feature. It has no live vehicle actuator and works
only against a private simulator frame. A later button-pad feature may transmit a verified vehicle
CAN command directly, but no message definition or safety contract exists yet.

## Decision

Remove every repository-owned CAN path between the coordinator and project devices before adding
the independent device API. Delete the custom protocol, registry, ISO-TP, old firmware, simulated
peers and their consumers.

The coordinator kernel keeps four responsibilities:

1. Decode and retain vehicle observations.
2. Apply operator and button intents to desired coordinator state.
3. Manage active profiles and curves.
4. Publish complete projections for browser SSE and device configuration.

Remove coordinator-owned button feedback, real-time Servotronic calculation and actuation,
Servotronic availability gating, applied-device state and the high-beam flash feature. Desired
steering state and profiles remain, but they do not imply that hardware applied them.

With no current coordinator-owned actuator, remove the application effect union, generic effect
executor, exact effect deadlines and effect-failure feedback. Retain vehicle CAN frame types,
receive paths, SocketCAN's basic send capability and simulation bus transmission where vehicle
simulation needs them. Do not retain an unused output abstraction or configured transmit authority.

A future vehicle action belongs to the component that performs it. It must have a named,
capture-backed command and an explicitly granted bounded transmitter. It does not revive the
project-device protocol or require the old effect system. The default live coordinator continues to
have no CAN transmit authority.

Simulation continues to exercise production boundaries that still exist. Simulated vehicle frames
cross the real vehicle decoder. Independent simulated devices use the production HTTP and SSE
handlers rather than virtual project-device CAN peers.

## Consequences

- The independent button-pad slice starts from a coordinator with no project-device transport.
- There is temporarily no button-pad input and no Servotronic output until later slices add their
  independent clients.
- The driving UI loses device availability, applied Servotronic and high-beam flash state that no
  longer describes a live capability.
- Existing prototype databases are replaced. A fresh database seeds one selected empty `Default`
  button profile with no product-specific assignments.
- The single-owner queue, typed inputs, immutable state, vehicle decoding and changed projections
  remain.
- Future CAN transmission starts from a specific vehicle feature instead of a dormant framework.
