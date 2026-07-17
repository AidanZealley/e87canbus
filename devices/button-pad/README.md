# Button-pad firmware

This Arduino Micro project implements the button-pad side of the generated
device-registry protocol v1 on MCP2515 K-CAN at 100 kbit/s.

`DEVICE_ID` defaults to `1` in the checked-in firmware source and is checked as
an unsigned 16-bit build-time value. An explicit compiler flag may override it
without redefining a project build flag for a separately provisioned bench
build. The 16-bit device session is read from
EEPROM, incremented once per boot, written back, and verified. The counter
wraps modulo 65536; zero is valid.

The firmware is nonblocking and uses `millis()` delta comparisons. It sends an
immediate HELLO, validates only matching WELCOME acknowledgements, sends an
immediate first heartbeat after acceptance, and renews its controller lease
with one-second heartbeats. Discovery, operational, controller-loss,
incompatible, and local-fault states select logical display modes for future
NeoTrellis rendering. ISO-TP payloads and button events are accepted only while
operational with a fresh controller lease.

Physical NeoTrellis scanning, logical-to-physical mapping, brightness/current
limits, rendering, bench testing, CAN collision capture, and in-car TX
authorization remain separate evidence gates. Successful compilation and
simulation do not establish those facts.
