# Devices

Each directory is an independently buildable firmware project for one physical CAN device. Name
directories after the device's purpose, not its current microcontroller family.

- `button-pad/` — NeoTrellis input and LED-output node.
- `steering-controller/` — reserved for the future Servotronic current controller.

Device firmware should own hardware scanning, fast local control, watchdogs, and failsafe behavior.
The coordinator owns vehicle-level decisions and sends desired state over CAN.

The button-pad milestone firmware automatically transmits test traffic and is bench-only. Do not
attach it to the car. Both planned custom devices ultimately attach to K-CAN at 100 kbit/s, subject
to collision, transceiver, termination, bitrate, isolation, and grounding validation.
