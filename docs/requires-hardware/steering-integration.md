# Remaining work: verified steering integration

The event-kernel and simulator hardening work is complete. Real steering actuation remains blocked
until vehicle and actuator behavior are backed by evidence. The simulator's synthetic speed frame,
dimensionless `0.0..1.0` command, zero-assistance fallback, and software watchdog are test tools;
none defines a physical protocol or safe state.

This work is governed by
[ADR 0006](../decisions/0006-evidence-gated-hardware-behavior.md).

## Evidence required before implementation

- Capture and verify the BMW speed arbitration ID, source network, payload scaling, cadence,
  counters, validity bits, standstill behavior, and loss/fault behavior.
- Characterize the steering actuator boundary: transport or electrical interface, command range and
  polarity, valve response, feedback, update cadence, and behavior when commands stop.
- Establish the electrical safe state for never-seen or stale speed, malformed traffic, ingress
  overflow, reader loss, process shutdown, power loss, and disconnection.
- Select and verify an independent hardware watchdog or actuator-controller timeout. Software
  fallback is not a substitute for coordinator silence.
- Validate every transmitted CAN ID against captures and document the explicit live TX grant and
  network budget it needs.

Store named captures and conclusions in `docs/candump_sessions/` and
`docs/decoded_messages.md`. Promote no candidate ID from placeholder status without that evidence.

## Implementation after the evidence gate

- Add the verified speed decoder to the network-and-ID router, preserving the ingress
  `received_at` timestamp.
- Add the verified actuator capability and effect using evidence-derived units, limits, refresh
  cadence, and safe command.
- Keep target selection in the pure application transition; the executor clamps and authorizes I/O
  but does not choose policy.
- Map never-observed or stale speed, malformed verified traffic, ingress overflow, reader failure,
  and shutdown to the agreed safe command and a diagnostic reason.
- Keep actuator refresh policy separate from the cosmetic CAN flood budget and satisfy the hardware
  watchdog independently.
- Leave live composition RX-only until collision checks, bench tests, and an explicit deployment
  configuration are reviewed.

## Acceptance gate

- Named captures reproduce the speed decoder across standstill, motion, loss, and fault cases.
- Bench tests cover no speed, fresh and stale speed, delayed queued frames, recovery, malformed
  traffic, reader failure, overflow, process kill, and actuator-command silence.
- The hardware watchdog reaches the verified electrical safe state without coordinator help.
- Captured command cadence fits the verified actuator policy and network allocation.
- A physical bypass and recovery procedure is documented.
- Default live configuration still exposes no transmitter or actuator capability.
