# ADR 0006: Keep unverified hardware behavior out of executable composition

- **Status:** Accepted
- **Date:** 2026-07-14

## Context

The desired steering and NeoTrellis features depend on facts the repository does not yet have:
vehicle captures, actuator electrical behavior, watchdog timing, board topology, pixel mapping, and
current limits. Plausible placeholder values would be easy to mistake for deployment authority.

## Decision

Vehicle-specific decoding, physical actuation, and physical LED rendering are gated on recorded,
reproducible evidence. Placeholder BMW IDs remain non-executable. Synthetic speed uses an
unmistakably simulation-only frame and the simulated actuator accepts only dimensionless commands;
neither can be composed live. Default live composition remains unable to transmit.

Physical rendering must use one explicit verified logical-to-physical map and enforce measured
brightness/current limits at the device boundary. Real steering work requires named vehicle
captures, a characterized actuator interface and electrical safe state, independent watchdog
behavior, collision validation, and an explicit live grant.

The current evidence checklists are maintained in
[verified steering integration](../requires-hardware/steering-integration.md) and
[verified physical NeoTrellis rendering](../requires-hardware/neotrellis-rendering.md).

## Consequences

- Simulation can validate software ordering and failure handling without making physical safety
  claims.
- Missing evidence is a deliberate implementation blocker, not a value to infer from community
  data or old notes.
- Hardware decisions become reviewable artifacts before they become constants, adapters, or live
  capabilities.
