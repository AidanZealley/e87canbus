# WeAct CAN485 ESP32 device board

- **Status:** Candidate board for future independent devices
- **Board family:** WeActStudio CAN485DevBoardV1 ESP32
- **Vendor source:** [WeActStudio.CAN485DevBoardV1_ESP32](https://github.com/WeActStudio/WeActStudio.CAN485DevBoardV1_ESP32)
- **Source revision checked:** `0865d397b931602d10bc740aa135b3a2c782340a`

## Project use

The planned independent button pad and Servotronic controller may use this board. They remain separate firmware projects
with separate roles and behavior. Sharing a board does not require a shared application framework.

The vendor specifies an ESP32-D0WD-V3, 8 MB flash and CH343P USB-to-serial bridge. Its Arduino
target is `ESP32 Dev Module`. The project uses an explicit 8 MB flash setting and a checked-in
partition table rather than relying on the generic target's defaults.

The vendor repository contains V1.0 and V1.1 hardware. V1.1 adds an 18-pin FPC connector for unused
ESP32 pins. The fixed onboard peripheral pins below are common to the vendor documentation. Check
the silkscreen before assigning an FPC pin to either device.

The vendor does not document PSRAM, so firmware must not depend on it.

## Fixed pin assignments

| Function | ESP32 pin | Project use |
|---|---:|---|
| CAN receive | GPIO26 | Vehicle CAN receive |
| CAN transmit | GPIO27 | Assigned to the transceiver, even when firmware uses listen-only mode |
| microSD chip select | GPIO13 | Unused |
| microSD clock | GPIO14 | Unused |
| microSD MOSI | GPIO15 | Unused |
| microSD MISO | GPIO2 | Unused |
| RS485 driver enable | GPIO17 | Unused |
| RS485 receive | GPIO21 | Unused |
| RS485 transmit | GPIO22 | Unused |
| VIN measurement | GPIO36 | Optional input-only voltage observation |
| Onboard WS2812 | GPIO4 | Diagnostic LED |
| Boot button | GPIO0 | Boot strap and local button |

The V1.1 FPC connector exposes GPIO37, GPIO38, GPIO39, GPIO34, GPIO35, GPIO32, GPIO33, GPIO25,
GPIO12, GPIO5, GPIO23, GPIO19, GPIO16 and GPIO18, plus power and ground. GPIO34 through GPIO39 are
input-only. Device wiring must also respect the ESP32 strapping behavior of GPIO0, GPIO2, GPIO5,
GPIO12 and GPIO15.

The button pad's NeoTrellis I2C pins and the Servotronic controller's output pins remain
device-specific wiring decisions. They must use the exposed pins without conflicting with the
fixed peripherals above.

## CAN interface

The board connects ESP32 TWAI RX and TX to an isolated CA-IS2062A CAN transceiver. The vendor
schematic also shows a common-mode choke, PESD2CAN protection and switchable split termination made
from two 62 ohm resistors with a 4.7 nF midpoint capacitor.

Both device roles initially use TWAI listen-only mode for vehicle observation. Disable the onboard
termination when attaching a device to an already terminated vehicle bus. Confirm the switch state
with a resistance measurement before connection rather than relying on switch markings.

The vendor example uses 500 kbit/s as a demonstration value. It is not a project default. The
button pad uses the verified K-CAN bitrate and the Servotronic controller uses the bitrate of its
capture-backed speed source.

## Internal flash layout

Both roles use this 8 MB partition contract:

| Name | Type | Offset | Size | Purpose |
|---|---|---:|---:|---|
| `nvs` | data, NVS | `0x009000` | `0x006000` | ESP-IDF runtime data |
| `otadata` | data, OTA | `0x00f000` | `0x002000` | Application selection metadata |
| `phy_init` | data, PHY | `0x011000` | `0x001000` | Radio calibration initialization |
| `e87id` | data, NVS | `0x012000` | `0x010000` | Provisioned identity and Wi-Fi credentials |
| `e87cfg` | data, NVS | `0x022000` | `0x010000` | Last accepted device configuration |
| `ota_0` | app, OTA 0 | `0x040000` | `0x3c0000` | Active application image |
| `ota_1` | app, OTA 1 | `0x400000` | `0x3c0000` | Reserved second application image |

The application partitions are 64 KiB aligned. The unused alignment gap before `ota_0` and the
final 256 KiB remain unallocated. This work does not add a filesystem partition or network firmware
update.

The microSD card is separate from internal flash and is not part of device operation or
provisioning. The vendor requires removing it while flashing. `e87ctl` must report that instruction
before invoking `esptool`.

## Power and vehicle connection

The vendor repository exposes a VIN input and a divided VIN measurement on GPIO36, but it does not
state a project-verified vehicle supply range. USB power is suitable for firmware and bench work.
Do not connect vehicle power until the board's accepted input range, fusing, grounding and transient
behavior have been verified for the installation.

The CAN isolation boundary does not establish safe power wiring or actuator isolation. Servotronic
output hardware still requires its own verified safe-state and electrical design.

## Primary vendor files

- [Vendor README at the checked revision](https://github.com/WeActStudio/WeActStudio.CAN485DevBoardV1_ESP32/blob/0865d397b931602d10bc740aa135b3a2c782340a/README.md)
- [V1.1 schematic](https://github.com/WeActStudio/WeActStudio.CAN485DevBoardV1_ESP32/blob/0865d397b931602d10bc740aa135b3a2c782340a/Hardware/WeAct-CAN485DevBoardV1_ESP32_V1.1%20SchDoc.pdf)
- [Vendor TWAI example](https://github.com/WeActStudio/WeActStudio.CAN485DevBoardV1_ESP32/blob/0865d397b931602d10bc740aa135b3a2c782340a/Examples/Arduino/CAN_TWAI/CAN_TWAI.ino)

