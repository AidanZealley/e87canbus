# Servotronic fan-bench controller

Minimal Arduino Pro Micro/MCP2515 firmware for proving the bench path from the
coordinator's synthetic speed frame to a bounded PWM output. It is deliberately
not rack or vehicle firmware.

The controller joins K-CAN at 100 kbit/s, registers using the existing
Servotronic HELLO/WELCOME/HEARTBEAT IDs (`0x705`–`0x707`), and accepts only the
extended synthetic ID `0x1fffff00`. Its payload must be exactly two bytes,
little-endian deci-km/h, in the range 0–3000. The compiled-in monotone curve
uses the coordinator's versioned Steffen/D3 `monotone-cubic-v1` algorithm,
schema-v1 speed grid and per-mille control points. After registration, the
coordinator may replace it with one complete validated curve in RAM over the
provisional `0x70A`/`0x70B` ISO-TP link. The fixed v1 message includes the exact
eight-point grid, per-mille values, activation revision, and CRC-32. Unsupported
versions, a wrong grid, increasing/out-of-range assistance, a bad CRC, or an
incomplete transfer leave the active curve unchanged. The AVR evaluates the
curve in binary32 and explicitly truncates the result to bounded 8-bit PWM duty.

The received curve is intentionally not written to EEPROM. A reset immediately
uses the compiled-in fallback; once the coordinator is available it reconciles
the SQLite-selected curve into RAM again. A successfully received RAM curve
continues to be used if the coordinator lease expires.

Output is zero at boot and while speed has never been seen, is invalid, or is
older than 500 ms. It is also zero on an
MCP2515 error/send failure, during CAN reinitialisation, and during/reset by the
hardware watchdog. A subsequent valid speed frame clears the invalid-frame
inhibit. Diagnostics are rate-limited to one line per second (or a state change).
Missing or stale speed is reported as an output inhibit in telemetry; it does
not mark the controller's registry heartbeat as a device fault.

## Wiring

| Pro Micro | MCP2515 / PWM board | Notes |
|---|---|---|
| VCC | MCP2515 VCC | Use a module compatible with the Pro Micro logic voltage |
| GND | MCP2515 GND and PWM input GND | Common signal ground unless input is isolated |
| D15/SCK | SCK | Hardware SPI |
| D16/MOSI | SI/MOSI | Hardware SPI |
| D14/MISO | SO/MISO | Hardware SPI |
| D10 | CS | Configurable with `CAN_CS_PIN` |
| D9 | PWM signal input | Configurable with `PWM_OUTPUT_PIN`; Timer1 PWM |
| CANH/CANL | Bench K-CAN | Correct termination required |

Feed the fan/output stage from a fused 12 V bench supply. Do **not** feed 12 V
to a Pro Micro logic pin. The default assumes an 8 MHz MCP2515 crystal
(`MCP2515_CLOCK`) and caps `analogWrite` at 180/255 (`PWM_DUTY_CEILING`). Override
these build defines in `platformio.ini` for the actual modules. Confirm whether
the chosen power board expects active-high PWM and whether its input is isolated.
Fit a hardware pull-down at the PWM-board input so it remains off while the Pro
Micro is unpowered, resetting, or has not configured its output pin.

## Build and test

```sh
cd devices/servotronic-controller
pio test -e native
pio run -e micro
```

Upload over USB after confirming the board and wiring:

```sh
pio run -e micro --target upload
```

If PlatformIO does not select the correct serial device, list candidates with
`pio device list` and provide the port explicitly, for example:

```sh
pio run -e micro --target upload --upload-port /dev/cu.usbmodem1101
```

The exact device name varies by host and USB port. A Pro Micro may briefly
enumerate under a different bootloader port after reset; rerun upload or specify
that bootloader port if automatic detection misses it.

For the bench, start the coordinator with the `bench` deployment, connect CAN,
then change speed through the simulation vehicle API. Verify duty falls as speed
rises. Silence speed traffic and verify output becomes zero within 500 ms; also
test coordinator shutdown, CAN disconnection, malformed/over-range speed,
controller reset, and recovery with a valid frame. Keep the fan disconnected
until the PWM polarity and safe-zero voltage have been measured.

## Limitations

PWM duty is **not 0.6 A closed-loop current limiting**. This firmware has no
current sensor, current feedback loop, over-current measurement, output-stage
diagnostics, rack-solenoid flyback design, or validated real BMW speed decoder.
A fan test demonstrates observable modulation and shutdown only; it does not
establish safe control of an inductive Servotronic valve. The synthetic extended
frame and K-CAN placement are bench-only, and the firmware is not vehicle-safe.
