# Devices

Each directory is an independently buildable firmware project for one physical CAN device. Name
directories after the device's purpose, not its current microcontroller family.

Each device README should document its current bench wiring with a pin-to-pin diagram or table.
Mark deliberately unused pins explicitly, and keep unverified vehicle-side connections separate
from confirmed bench wiring.

- `button-pad/` — NeoTrellis input and LED-output node.
- `servotronic-controller/` — reserved for the future Servotronic current controller.

Device firmware should own hardware scanning, fast local control, watchdogs, and failsafe behavior.
The coordinator owns vehicle-level decisions and sends desired state over CAN.

The button-pad firmware performs the version 1 device handshake and is hardware-validation-gated.
It does not claim physical NeoTrellis rendering, collision validation, or in-car readiness. Do not
attach it to the car. Both planned custom devices ultimately attach to K-CAN at 100 kbit/s,
subject to collision, transceiver, termination, bitrate, isolation, and grounding validation.

The coordinator sends virtual-pad RGB snapshots over the bounded ISO-TP link. Physical NeoTrellis
topology, logical-to-physical mapping, brightness, and current limits remain deliberately deferred.
