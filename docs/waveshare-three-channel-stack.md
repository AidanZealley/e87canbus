# Coordinator Waveshare three-channel CAN stack

This document records why the coordinator Raspberry Pi CAN stack works, how Linux discovers it,
and the electrical constraints that must remain true. It is the hardware rationale behind
`scripts/setup_coordinator.sh`, not a substitute for the executable two-host procedure in
[the deployment runbook](../deploy/README.md).

The console does not use this stack. It uses only the 2-CH CAN HAT+ first controller for
receive-only K-CAN; see [console wiring](wiring.md#console-can-and-ethernet).

## Supported boards

The stack combines:

1. A Waveshare 2-CH CAN HAT+ in its factory SPI1 configuration.
2. The original Waveshare RS485 CAN HAT v2.1 using SPI0 CE0.

Both use an MCP2515 Classic CAN controller and an SPI connection to the Pi. The dual HAT uses two
MCP2515/SN65HVD230 paths; the original HAT uses one MCP2515/SN65HVD230 path. Linux's in-tree
`mcp251x` driver exposes each controller as a separate SocketCAN network interface.

Primary hardware references:

- [Waveshare 2-CH CAN HAT+ wiki](https://www.waveshare.com/wiki/2-CH_CAN_HAT%2B)
- [Waveshare 2-CH CAN HAT+ schematic](https://files.waveshare.com/wiki/2-CH-CAN-HAT%2B/2-CH_CAN_HAT%2B.pdf)
- [Waveshare RS485 CAN HAT wiki](https://www.waveshare.com/wiki/RS485_CAN_HAT)
- [Raspberry Pi device-tree overlay reference](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README)

## Why the boards can be stacked

An SPI peripheral needs the shared clock/data pins for its SPI controller, a unique chip-select, and
an interrupt GPIO. The boards use different SPI controllers and non-overlapping interrupts:

| Network role | Board channel | SPI bus and select | SPI GPIOs | Interrupt | Crystal |
|---|---|---|---|---:|---:|
| K-CAN | Original HAT CAN | SPI0 CE0 (`spi0.0`) | BCM9/10/11 | BCM25 | 12 MHz |
| PT-CAN | HAT+ CAN0 | SPI1 CE1 (`spi1.1`) | BCM19/20/21 | BCM22 | 16 MHz |
| F-CAN | HAT+ CAN1 | SPI1 CE2 (`spi1.2`) | BCM19/20/21 | BCM13 | 16 MHz |

The two HAT+ controllers intentionally share SPI1 MISO, MOSI, and clock. CE1 and CE2 ensure that
only one responds at a time. The original controller is on SPI0, so it shares neither those data
pins nor their chip-selects. BCM25, BCM22, and BCM13 provide distinct active-low interrupt inputs.

The HAT+ factory configuration is therefore compatible with the original HAT without resistor or
solder changes. It must remain configured for:

- Logic level: 3.3V
- CAN0: SPI1 CE1 and interrupt BCM22
- CAN1: SPI1 CE2 and interrupt BCM13

The original HAT's unused RS485 transceiver occupies the primary UART on BCM14/15, so those pins
cannot also carry the bidirectional coordinator-panel link. The panel instead uses UART3 on BCM4/5.
On the original HAT's factory automatic-direction configuration, the optional BCM4 `RSE` link is
not populated; do not fit that link or enable UART3 CTS/RTS. Setup continues to remove Waveshare's
unnecessary header `i2c0` overlay so it does not claim that separate internal allocation. The
coordinator itself is headless.

The HAT+ goes directly on the Pi and the original HAT stacks above it. Correct spacers are required
to prevent terminal blocks or solder joints touching another board or the Pi connectors.

## Device-tree configuration

The managed physical-profile configuration is:

```ini
dtparam=spi=on
dtoverlay=spi1-3cs
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
dtoverlay=mcp2515,spi1-1,oscillator=16000000,interrupt=22,speed=10000000
dtoverlay=mcp2515,spi1-2,oscillator=16000000,interrupt=13,speed=10000000
```

The lines have separate jobs:

- `dtparam=spi=on` enables the primary SPI controller used by the original HAT.
- `dtoverlay=spi1-3cs` enables SPI1 and its CE0/CE1/CE2 GPIO allocation. CE1 and CE2 are used here;
  CE0 remains unused by these CAN controllers.
- `mcp2515-can0` describes the original fixed SPI0 CE0 controller.
- The two generic `mcp2515` overlays place controllers at SPI1 CE1 and CE2.

The older fixed overlay calls its maximum-SPI-clock parameter `spimaxfrequency`; the generic
overlay calls it `speed`. The `oscillator` values describe the physical MCP2515 crystals and must
not be confused with CAN bus bitrates. SocketCAN bitrates are applied later by systemd.

The generic overlay disables the corresponding `spidev` node so the kernel MCP2515 driver, rather
than a userspace SPI client, owns each selected device.

Waveshare's example also enables `dtoverlay=i2c0`, but neither MCP2515 uses I2C, so setup
deliberately removes it. The HAT+ identification EEPROM is not used at runtime.

No Waveshare BCM2835, WiringPi, or Python demo library is required. The project uses the kernel
driver, SocketCAN, `ip`, `can-utils`, and `python-can` through its SocketCAN adapter.

## Linux interface names and validation

The CAN subsystem initially allocates names using the pattern `can%d`; the device-tree overlay name
does not guarantee a permanent physical-to-number mapping. A project-owned udev rule renames each
interface from its SPI parent, producing this stable mapping on the supported Pi stack:

```text
kcan -> spi0.0
ptcan -> spi1.1
fcan -> spi1.2
```

The setup script validates the resolved `/sys/class/net/INTERFACE/device` parent for every interface
before enabling the controller. A missing controller or different mapping fails closed. This is
what makes the application's stable semantic assignment safe:

| Interface | Application network | Service bitrate |
|---|---|---:|
| `kcan` | K-CAN | 100 kbit/s |
| `ptcan` | PT-CAN | 500 kbit/s |
| `fcan` | F-CAN | 500 kbit/s |

Dedicated systemd units apply those bitrates, set automatic recovery with `restart-ms 100`, and
raise the links before the physical controller service. Bench and car use the same complete
hardware topology. Bench retains a K-CAN-only application transmit grant; car grants no
application CAN transmission. Simulator disables the physical CAN services.

## Isolation and grounds

The HAT+ isolates its logic/CAN side from the Pi using digital isolation and an isolated supply.
Its schematic shows both CAN connectors using the same isolated-side `SGND` and supply domain.
Consequently:

- Both connectors are logically separate CAN networks with independent controllers and
  transceivers.
- Both are isolated from the Pi-side logic domain.
- They are **not galvanically isolated from each other** because their connector ground/reference
  domain is shared.

The original RS485 CAN HAT is documented as non-isolated, so its CAN-side reference is tied to the
Pi-side ground. Treat all three connectors according to those actual domains rather than assuming
that three SocketCAN interfaces means three mutually isolated electrical systems.

Waveshare exposes a `G`/ground connection alongside CAN-H and CAN-L on the HAT+. Whether and where
to connect it depends on the bench or vehicle grounding design. Do not improvise ground paths
between vehicle networks; validate the intended reference and isolation arrangement first.

## Power

The HAT+ can accept 5V or a 7–36V external input and its schematic includes a regulator capable of
feeding the Pi 5V rail. During initial setup, power only through the Pi's normal connector and leave
the HAT+ external input disconnected. Do not attach two supplies until their power-path and
back-feed behavior have been deliberately reviewed.

The HAT+ logic-level jumper must be at 3.3V for a Raspberry Pi. The 5V position is intended for
other host logic and is not safe as the Pi GPIO level selection.

## Termination and bus topology

Each physical CAN network needs termination only at its two ends. The HAT+ provides a switchable
120Ω terminator per channel. Enable it only when that connector is an endpoint. When tapping an
already terminated bus, leave it disabled.

With all nodes powered off, a correctly terminated bus with two 120Ω endpoints normally measures
approximately 60Ω between CAN-H and CAN-L. Approximately 40Ω suggests that a third 120Ω terminator
has been added. Interface creation and SPI validation do not prove CAN-H/CAN-L polarity,
transceiver operation, grounding, termination, arbitration, or successful acknowledgements; those
require a correctly wired second CAN node and observed traffic.

## Maintained boundary

The software configuration can verify controller discovery, SPI parents, link setup, services, and
application health. It cannot verify physical jumper positions, oscillator markings, clearance,
external power, vehicle connector pinouts, ground safety, or termination. Those remain explicit
preflight checks in the deployment and wiring documentation.
