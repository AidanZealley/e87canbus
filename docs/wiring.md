# Wiring

All pinouts are pending ISTA and candump verification.

## K-CAN iDrive Connector

Pending connector identification and pinout confirmation.

## PT-CAN and F-CAN Connectors

Pending PT-CAN and DSC/F-CAN connector pinout confirmation.

## Pi CAN Bring-Up

The hardware allocation, overlay mechanics, electrical domains, and stacking rationale are
documented in [Waveshare three-channel CAN stack](waveshare-three-channel-stack.md).

Required Pi stack and assignments:

- Original Waveshare RS485 CAN HAT v2.1 on SPI0 CE0, 12 MHz oscillator and interrupt BCM `25`:
  `can0` / K-CAN at `100000`.
- Waveshare 2-CH CAN HAT+ CAN0 on SPI1 CE1, 16 MHz oscillator and interrupt BCM `22`:
  `can1` / PT-CAN at `500000`.
- Waveshare 2-CH CAN HAT+ CAN1 on SPI1 CE2, 16 MHz oscillator and interrupt BCM `13`:
  `can2` / F-CAN at `500000`.
- Set the HAT+ logic-level jumper to 3.3 V. Its factory SPI1 CE1/CE2 selections avoid the original
  HAT's SPI0 CE0 connection.
- Arduino Micro / ATmega32U4 with MCP2515 CS pin `10`.
- Button-pad Pro Micro pin-to-pin wiring is documented in
  [`devices/button-pad/README.md`](../devices/button-pad/README.md#pro-micro-to-mcp2515-wiring).
- Button-pad MCP2515 library clock setting currently `MCP_8MHZ` for the module's 8 MHz crystal.

Wire CAN-H to CAN-H, CAN-L to CAN-L, and ensure the bench bus has correct termination.

Setup verifies `can0` → `spi0.0`, `can1` → `spi1.1`, and `can2` → `spi1.2`. Actual vehicle bitrate,
compatible transceivers, grounding, isolation, and termination must be verified before physical
connection.

## Servotronic Solenoid Driver

No physical steering output is designed or approved. Command transport, electrical range and
polarity, valve behavior, feedback, safe state, watchdog behavior, and controller topology all
remain unknown. Keep project hardware disconnected from the actuator until those properties are
verified and documented; only then can an output circuit be selected and reviewed.

## Arduino/NeoTrellis Node

First milestone firmware does not initialize Trellis. It sends alternating button-event frames on
`0x700` automatically every second. It receives provisional ISO-TP traffic on `0x708`/`0x709`; the
firmware transport compiles but physical RGB snapshot consumption and rendering remain deferred.
Physical topology, logical-to-pixel mapping, brightness, and current limits remain unverified and
unimplemented. This firmware is hardware-validation-gated and must not be attached to the car while
automatic transmission remains enabled; both IDs still require collision validation.
