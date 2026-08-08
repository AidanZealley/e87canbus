# Coordinator panel

PlatformIO firmware for the Adafruit QT Py RP2040, NeoPixel Driver BFF, five-pixel indicator, and
momentary hotspot button. The firmware renders the Pi's semantic state and reports debounced button
presses; hotspot policy remains on the Pi.

## Wiring

Confirm the labels and orientation on the assembled boards before making the loom.

| Function | QT Py RP2040 | Connection |
| --- | --- | --- |
| Power | `5V` | Pi 5 V, subject to the back-power check below |
| Ground | `GND` | Pi ground and button ground |
| UART transmit | `TX` | Pi BCM15/RXD |
| UART receive | `RX` | Pi BCM14/TXD |
| NeoPixel data | `A3` | NeoPixel Driver BFF data input |
| Hotspot button | `A0` | Momentary switch to ground; internal pull-up enabled |

Do not connect QT Py USB-C while the Pi power harness is attached until competing-supply and
back-power behavior has been resolved. The UART is 3.3 V logic. The strip must contain exactly five
WS2812-compatible pixels, use a short data run, and share ground with the Pi and QT Py.

## Protocol and safety behavior

UART runs at 115200 baud, 8-N-1. Messages are newline-delimited ASCII and implement protocol v1:

```text
PANEL 1 HELLO
PANEL 1 BUTTON <uint32 sequence>
PANEL 1 STATE <starting|ready|hotspot_waiting|hotspot_connected|fault|off>
```

Input is bounded to 63 characters. The panel shows the travelling white startup state immediately,
allows 60 seconds for the first valid state, and shows red after a two-second established-link
heartbeat timeout. A later valid state recovers immediately. `off` remains latched without a
heartbeat so graceful Pi shutdown stays dark.

All colour channels are scaled through the compile-time `BRIGHTNESS_CEILING` in `src/main.cpp`.
Change that ceiling only after measuring the assembled strip and diffuser.

## Build and test

```bash
pio run -e qtpy_rp2040
pio test -e native
```

The native tests exercise parsing, line bounds and recovery, debounce, display selection,
animations, heartbeat behavior, brightness limiting, and sequence wrapping. Board flashing and
NeoPixel/UART electrical behavior still require the Phase 2 bench procedure.
