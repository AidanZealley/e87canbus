# Wiring

All pinouts are pending ISTA and candump verification.

## K-CAN iDrive Connector

Pending connector identification and pinout confirmation.

## PT-CAN and F-CAN Connectors

Pending PT-CAN and DSC/F-CAN connector pinout confirmation.

## Bench CAN

Confirmed bench defaults:

- Raspberry Pi 4 with Waveshare RS485 CAN HAT v2.1.
- HAT oscillator marking `12000`, so use `oscillator=12000000`.
- MCP2515 overlay interrupt BCM `25`.
- `can0` bench bitrate `100000`.
- Arduino Micro / ATmega32U4 with MCP2515 CS pin `10`.
- Arduino MCP2515 library clock setting currently `MCP_16MHZ`.

Wire CAN-H to CAN-H, CAN-L to CAN-L, and ensure the bench bus has correct termination.

The intended Pi assignment is K-CAN on `can0`, PT-CAN on `can1`, and F-CAN on `can2`.
Actual vehicle bitrate, compatible transceivers, grounding, isolation, and termination must be
verified before physical connection.

## Servotronic Solenoid Driver

Pending solenoid resistance measurement and current-driver selection. Do not drive the solenoid directly from GPIO.

## Arduino/NeoTrellis Node

First milestone firmware does not initialize Trellis. It sends alternating button-event frames on
`0x700` automatically every second and prints LED-update frames received on `0x701`. This firmware
is bench-only and must not be attached to the car while automatic transmission remains enabled.
