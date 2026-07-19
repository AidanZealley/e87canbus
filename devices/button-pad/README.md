# Button-pad firmware

This Arduino Micro project implements the button-pad side of the generated
device-registry protocol v1 on MCP2515 K-CAN at 100 kbit/s.

The current hardware-validation setup is a 5 V/16 MHz Pro Micro with an MCP2515 module
using an 8 MHz crystal. The firmware's `MCP_8MHZ` CAN-controller setting refers
to the MCP2515 module crystal and is independent of the Pro Micro CPU clock.

## Pro Micro to MCP2515 wiring

```text
5 V Pro Micro                         MCP2515 module

VCC / 5V  -------------------------- VCC
GND       -------------------------- GND
D15 / SCK -------------------------- SCK
D16 / MOSI ------------------------- SI / MOSI
D14 / MISO ------------------------- SO / MISO
D10       -------------------------- CS / C̅S
                                      INT  (not connected)
```

| MCP2515 module | Pro Micro |
|---|---|
| `VCC` | `VCC/5V` |
| `GND` | `GND` |
| `SCK` | `D15` / hardware SCK |
| `SI` or `MOSI` | `D16` / hardware MOSI |
| `SO` or `MISO` | `D14` / hardware MISO |
| `CS` or `C̅S` | `D10` |
| `INT` | Not currently required; leave disconnected |

This pinout is for the current 5 V Pro Micro bench build. The firmware polls the MCP2515, so it
does not configure or read an interrupt pin. Connect the module's CAN-H and CAN-L terminals only
to a correctly terminated bench CAN bus; vehicle-side wiring remains unverified.

`DEVICE_ID` defaults to `1` in the checked-in firmware source and is checked as
an unsigned 16-bit build-time value. An explicit compiler flag may override it
without redefining a project build flag for a separately provisioned hardware
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
limits, rendering, collision capture, and in-car TX authorization remain
separate evidence gates. Successful compilation and simulation do not establish
those facts.
