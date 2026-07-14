# ADR 0002: Control output with explicit capabilities and a network-wide bound

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

The early runtime could transmit provisional frames under repository defaults, and its temporary
per-frame limiter did not describe a useful network safety boundary. Authorization, flood control,
and application decisions also lived at different writable points.

## Decision

The default live composition has no transmitter capability on any CAN network. A composition must
explicitly grant a network transmitter, and every CAN effect passes through the sole
`EffectExecutor`/`SafeCanTransmitter` boundary.

Each granted network has one sliding-window budget shared by every arbitration ID. The default
ceiling is 20 coordinator frames in any rolling second. Excess frames are logged and dropped; they
are never queued or replayed. Actuator refresh policy is separate because it must eventually be
derived from verified watchdog and hardware timing.

## Consequences

- Merely constructing the runtime cannot confer transmit authority.
- Traffic on one arbitration ID consumes the same finite budget as traffic on every other ID on
  that network.
- Later complete-state messages can converge a device after a drop without replaying stale output.
- Application-level denial is not SocketCAN or hardware listen-only mode; deployments should use
  those as an additional defense.
