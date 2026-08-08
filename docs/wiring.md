# Wiring

Vehicle pinouts are pending ISTA and candump verification.

## Coordinator Panel

The supported physical coordinator is a Raspberry Pi 4 Model B. The QT Py RP2040 and NeoPixel
Driver BFF mount back-to-back and drive exactly five 5 V WS2812B- or SK6812-compatible pixels.
Connect the detachable four-wire Pi 4 harness as follows:

| Function | Pi | QT Py / BFF |
|---|---|---|
| Pi transmit | BCM14 / TXD, physical pin 8 | RX |
| Pi receive | BCM15 / RXD, physical pin 10 | TX |
| Power | Regulated 5 V, physical pin 2 or 4 | BFF/QT Py 5 V |
| Ground | Ground, for example physical pin 6 | Ground |

UART is 3.3 V logic at 115,200 baud. Cross transmit to receive as shown. Never connect vehicle
12 V or Pi 5 V to either UART signal.

The button is normally open between QT Py A0 and ground; firmware enables the internal pull-up.
Pixel data is QT Py A3 through the BFF level shifter. Wire the power leg in this order:

```text
Pi 5 V -- 500 mA fuse -- 1 A Schottky diode -- QT Py/BFF 5 V
```

Use a 1N5817 or 1N5819 with its anode toward the Pi and striped cathode toward the QT Py. The fuse,
diode, UART, and ground must all be part of the detachable harness. Disconnect the complete harness
before attaching QT Py USB-C for upload or service; never power it from the Pi and USB together.

Before installation, bench-check harness polarity and continuity, `/dev/serial0` TX/RX, the five
pixel order and colours, brightness, button debounce, heartbeat fault/recovery, graceful off,
hotspot association/cancellation/disconnect, and the Ethernet forwarding block. These checks remain
pending until the assembled hardware is available. Do not add further power switching, capacitors,
data protection, or live-USB isolation unless the bench demonstrates a problem.

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
