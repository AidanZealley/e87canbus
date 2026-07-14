# ADR 0003: Keep simulation on the production control path

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

A simulator that injects domain events or edits application state directly can demonstrate behavior
that the live decoder, kernel, effect executor, or output policy cannot actually perform. Concurrent
HTTP commands, timers, resets, and WebSocket sends can also reorder state unless ownership is
explicit.

## Decision

Browser commands operate simulated external devices. Those devices emit encoded CAN frames that
traverse ingress timestamping, routing, transition, commit, effect execution, network policy, and
device decoding. Simulation-only protocol definitions and actuator capabilities are isolated from
live composition.

One asynchronous owner serializes a bounded simulation command queue, timers, resets, kernel
commits, and publication. Snapshots use the kernel revision; trace identity is `(session_id,
sequence)` so reset-local sequence numbers remain unambiguous. WebSocket sends are bounded and a
stalled peer is removed. Fatal output health terminates normal commands until reset creates a new
session.

## Consequences

- End-to-end simulator tests exercise the same control and safety boundaries as live inputs.
- The API cannot inject `DomainEvent` or `ApplicationState` values.
- Overload is reported instead of growing an unbounded command backlog.
- Synthetic speed and the dimensionless steering actuator prove software semantics only; they do
  not imply a verified vehicle protocol or physical safe state.
