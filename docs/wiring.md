# Wiring

All pinouts are pending ISTA and candump verification.

## K-CAN iDrive Connector

Pending connector identification and pinout confirmation.

## F-CAN DSC Connector

Pending DSC connector pinout confirmation.

## Bench CAN

Confirmed bench defaults:

- Raspberry Pi 4 with Waveshare RS485 CAN HAT v2.1.
- HAT oscillator marking `12000`, so use `oscillator=12000000`.
- MCP2515 overlay interrupt BCM `25`.
- `can0` bench bitrate `500000`.
- Arduino Micro / ATmega32U4 with MCP2515 CS pin `10`.
- Arduino MCP2515 library clock setting currently `MCP_16MHZ`.

Wire CAN-H to CAN-H, CAN-L to CAN-L, and ensure the bench bus has correct termination.

Vehicle K-CAN and F-CAN interface assignments are still pending capture and verification.

## Servotronic Solenoid Driver

Pending solenoid resistance measurement and current-driver selection. Do not drive the solenoid directly from GPIO.

## Arduino/NeoTrellis Node

First milestone firmware does not initialize Trellis. It only sends alternating button-event frames on `0x700` and prints LED-update frames received on `0x701`.
