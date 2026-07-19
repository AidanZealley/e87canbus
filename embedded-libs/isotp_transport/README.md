# ISO-TP transport

This repository-owned PlatformIO library wraps `isotp-c` for the Arduino firmware projects.
Each `IsoTpTransport` is bound to the CAN-frame sender passed to its constructor, so transports
in the same firmware may use different CAN controllers.

Calls into a transport must be made serially from the main loop. Do not call it from an interrupt
or concurrently from multiple tasks: `isotp-c` exposes one process-wide transmit callback, and
the wrapper selects the appropriate instance sender for the duration of each `isotp-c` call.
