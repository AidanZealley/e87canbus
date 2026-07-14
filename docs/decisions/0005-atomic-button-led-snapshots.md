# ADR 0005: Represent button-pad LEDs as atomic snapshots

- **Status:** Accepted
- **Date:** 2026-07-14

## Context

Indexed LED mutations required several frames to describe one application decision, exposed partial
device state, and interacted poorly with a network-wide drop policy. All repository-owned
participants could be changed together because the protocol remains provisional.

## Decision

The application derives one immutable state containing exactly 16 known LED colours. A changed
projection emits at most one `SetButtonLeds` effect, encoded as one `0x701` DLC-8 frame. For each
byte, the even LED index occupies the low nibble and the odd index the high nibble.

Firmware, simulation, API, and frontend validate the complete value before replacing all 16
positions. A wrong length or unknown colour rejects the whole snapshot and preserves the previous
state. The former indexed DLC-2 path is not retained as a compatibility codec.

## Consequences

- One application LED decision consumes one network-window entry.
- Dropping a snapshot does not create a partial update; the next accepted snapshot converges the
  device.
- Logical LED state is idempotent and has one publication shape across the system.
- Physical NeoTrellis mapping, brightness, and current limits remain a separate evidence-backed
  boundary.
