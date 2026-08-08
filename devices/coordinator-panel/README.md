# Coordinator-panel firmware

This PlatformIO project targets the Adafruit QT Py RP2040 mounted with an Adafruit NeoPixel Driver
BFF. It drives exactly five WS2812B/SK6812-compatible pixels and implements only the coordinator
panel's fixed newline-delimited UART protocol.

## Connections

| Function | QT Py connection |
|---|---|
| Button | A0 to ground; firmware enables the internal pull-up |
| NeoPixel data | A3 through the NeoPixel Driver BFF level shifter |
| UART from Pi | Pi BCM14/TXD to the QT Py pin labelled RX |
| UART to Pi | Pi BCM15/RXD from the QT Py pin labelled TX |
| Power | Pi regulated 5 V and ground to QT Py/BFF |

The UART is 3.3 V at 115,200 baud. Never connect vehicle 12 V or 5 V to a UART signal. Feed the
installed panel through `Pi 5 V -> 500 mA fuse -> 1 A Schottky diode -> QT Py/BFF 5 V`, using a
1N5817 or 1N5819 with its anode toward the Pi and striped cathode toward the QT Py.

**Disconnect the complete Pi power/UART harness before connecting USB-C.** USB is only for flashing
and service; it is not the installed transport.

## Build, test, and upload

From the repository root:

```sh
cd devices/coordinator-panel
pio test -e native
pio run -e qtpy_rp2040
cd ../..
./scripts/coordinator_panel_upload.sh
```

If PlatformIO cannot select the USB serial device, pass it explicitly:

```sh
UPLOAD_PORT=/dev/ttyACM0 ./scripts/coordinator_panel_upload.sh
```

The first flash or firmware recovery may require entering the RP2040 USB bootloader manually:
hold BOOT, tap RESET, then release BOOT before retrying the upload. The exact device path varies by
host and USB port.

Compilation and native tests do not validate physical pixel order/colour, perceived brightness,
3.3 V UART, button wiring, or heartbeat behaviour on the assembled harness. Complete those checks
on a fused bench supply with the Pi harness disconnected whenever USB-C is attached.
