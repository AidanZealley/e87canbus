# ADR 0009: Isolate coordinator accessories from control

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

The coordinator panel displays process and hotspot status and provides one hotspot button. Both the
physical panel and its browser simulation need the same behaviour, but neither is part of vehicle
control. Letting panel communication or NetworkManager work enter the controller kernel would add
another state owner and allow an optional accessory to interfere with CAN processing.

The physical UART has an additional timing constraint: its one-second status heartbeat must not be
delayed by potentially slow hotspot observation or commands. Button readiness must still reflect
the coordinator state when the physical press arrives, rather than when queued work eventually runs.

## Decision

The panel and hotspot are accessory services composed beside the controller kernel. They consume a
read-only coordinator-status projection and cannot submit controller inputs, mutate controller
state, change readiness, or interrupt CAN processing when they fail.

Physical and simulated compositions use the same semantic panel and hotspot services. They replace
only the UART, NetworkManager, and in-memory edges; display and button rules are not duplicated in
adapters or the frontend.

The physical composition keeps UART parsing and heartbeat output under one port owner, independent
of hotspot work. A complete physical button event captures the current coordinator status at UART
receipt, and the shared panel service applies its readiness gate to that captured status. This
prevents a queued press from being accepted or rejected because readiness changed while unrelated
hotspot work was in progress.

## Consequences

- Accessory failure can produce a panel indication and diagnostics without becoming a controller
  health failure.
- Simulation demonstrates the production rules without simulating UART bytes, RP2040 execution, or
  NetworkManager internals.
- The UART heartbeat remains bounded independently of networking latency.
- New coordinator accessories should not enter the kernel unless they gain a genuine vehicle-control
  responsibility requiring ordered controller input.
