# Phase 3 — Verified Physical NeoTrellis Rendering

## Status

**Blocked until the button-pad hardware boundary is verified.** The atomic CAN snapshot migration in
phases 1–2 does not require inventing this information.

## Required evidence

Record all of the following before implementation:

1. Exact NeoTrellis product/revision and library supported by the deployed microcontroller.
2. I2C addresses, tile ordering, orientation, and logical button-to-pixel mapping for all 16 LEDs.
3. Supply voltage, available current, grounding, brightness ceiling, and worst-case current with all
   pixels at the brightest allowed colour.
4. Startup state and behavior during CAN silence, malformed snapshots, bus-off, and coordinator
   restart.
5. A bench procedure that can verify each logical index without connection to the vehicle.

Store the conclusions in the device and wiring documentation. Photographs or wiring diagrams should
identify orientation clearly enough to reproduce the mapping.

## Implementation

- Implement one renderer accepting the already validated complete 16-colour state.
- Map logical positions to verified physical pixels in one explicit table; do not distribute index
  transformations through callbacks.
- Clamp brightness/current at the verified hardware boundary without changing logical colours in
  coordinator state.
- Render only after a complete snapshot has passed protocol validation.
- Keep the previous physical output unchanged on malformed frames.
- Decide and document the safe physical behavior during prolonged coordinator silence; do not infer
  it from the cosmetic CAN rate policy.

## Acceptance criteria

- A bench test identifies every logical index and expected physical pixel.
- All-off and worst-case allowed snapshots remain within the verified current budget.
- Malformed traffic cannot partially change physical output.
- Simulation and physical rendering consume the same logical 16-colour ordering.
- Backend, frontend, generated-protocol, firmware, and documented hardware checks pass.
