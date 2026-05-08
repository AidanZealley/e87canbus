# Wiring

All pinouts are pending ISTA and candump verification.

## K-CAN iDrive Connector

Pending connector identification and pinout confirmation.

## F-CAN DSC Connector

Pending DSC connector pinout confirmation.

## Pi CAN Interfaces

Planned defaults:

- `can0`: K-CAN at 100 kbit/s.
- `can1`: F-CAN at 500 kbit/s.

Interface hardware and overlay configuration are future work.

## Servotronic Solenoid Driver

Pending solenoid resistance measurement and current-driver selection. Do not drive the solenoid directly from GPIO.

## Arduino/NeoTrellis Node

Pending final ATmega32U4 board, MCP2515 CS pin, INT pin, and NeoTrellis I2C wiring confirmation.

