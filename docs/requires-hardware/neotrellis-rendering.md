# Remaining work: verified physical NeoTrellis rendering

Atomic 16-colour LED snapshots are implemented across the application, CAN protocol, firmware
storage, simulator, API, and frontend. Physical NeoTrellis output remains blocked because the board
topology and electrical limits have not been recorded. Do not infer them from library examples.

This work is governed by
[ADR 0005](../decisions/0005-atomic-button-led-snapshots.md) and
[ADR 0006](../decisions/0006-evidence-gated-hardware-behavior.md).

## Evidence required before implementation

- Identify the exact NeoTrellis product/revision and library supported by the deployed
  microcontroller.
- Record I2C addresses, tile order and orientation, and the logical button-to-pixel mapping for all
  16 positions. Include an orientation photograph or reproducible wiring diagram.
- Measure supply voltage, available current, grounding, a safe brightness ceiling, and worst-case
  current with every pixel at the brightest allowed colour.
- Decide the physical startup state and behavior during CAN silence, malformed snapshots, bus-off,
  and coordinator restart.
- Write a bench procedure that identifies every logical index without connecting the device to the
  vehicle.

Record the conclusions in `devices/button-pad/README.md` (create it if needed) and
`docs/wiring.md` before changing the renderer.

## Implementation after the evidence gate

- Implement one renderer that accepts the already validated complete 16-colour state.
- Put the verified logical-to-physical mapping in one explicit table; do not distribute index
  transforms through callbacks.
- Enforce measured brightness/current limits at the firmware boundary without changing the
  coordinator's logical colours.
- Render only after all eight payload bytes and all 16 colour nibbles have passed validation.
- Preserve the previous physical output after malformed traffic.
- Implement the documented safe behavior for prolonged coordinator silence independently of the
  cosmetic CAN rate policy.

## Acceptance gate

- A bench test identifies every logical index and expected physical pixel.
- All-off and worst-case allowed snapshots stay within the measured current budget.
- Malformed frames cannot partially change stored or physical output.
- Simulation and hardware use the same even-index-low, odd-index-high logical ordering.
- Backend, frontend, protocol-generation, firmware-build, and documented hardware checks pass.
