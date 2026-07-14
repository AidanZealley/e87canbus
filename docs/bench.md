# Bench CAN Ping-Pong

This milestone validates Pi-to-Arduino CAN transport before any car wiring.

## Hardware Defaults

- Raspberry Pi 4 with Waveshare RS485 CAN HAT v2.1.
- HAT oscillator marking `12000`: use `oscillator=12000000`.
- Overlay interrupt: BCM `25`.
- Bench CAN bitrate: `100000` (the eventual K-CAN rate).
- Arduino Micro / ATmega32U4 with MCP2515 on CS pin `10`.
- Arduino MCP2515 firmware clock setting: `MCP_16MHZ`.

> **Bench only:** the current firmware transmits a test button frame every second without user
> input. Never attach this firmware to the car. Remove and verify all automatic transmission
> behavior before any in-car connection.

## Protocol

- Arduino sends button events on `0x700`: `[button_index, state]`.
- `state=0` means released; `state=1` means pressed.
- Pi replies with one complete 16-colour LED snapshot on `0x701` (DLC 8). Each byte packs the even
  LED in its low nibble and the following odd LED in its high nibble.
- `colour=2` means green; `colour=0` means off. All unspecified bench positions remain off.

## Run Locally On The Pi

```bash
sudo ./scripts/bench_can_up.sh
uv run e87canbus-bench-pingpong --interface can0
```

The Pi reports each complete snapshot it sends. The first payload is `02 00 00 00 00 00 00 00`
(button 0 green); the next is all zeroes (all LEDs off).

```text
sent complete LED snapshot: colours=green,off,off,off,off,off,off,off,off,off,off,off,off,off,off,off
sent complete LED snapshot: colours=off,off,off,off,off,off,off,off,off,off,off,off,off,off,off,off
```

The expected Arduino serial logs alternate:

```text
sent button event index=0 state=pressed
received LED snapshot colours=2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
sent button event index=0 state=released
received LED snapshot colours=0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
```

Bring the bench CAN interface down with:

```bash
sudo ./scripts/bench_can_down.sh
```

## No Hardware Available

Run the in-process simulator on macOS, Linux, or CI:

```bash
uv run e87canbus-sim-bench
```

The simulator runs the existing Pi bench logic against a simulated NeoTrellis node. It alternates
button press and release frames and atomically replaces the node's complete LED state from the
snapshots sent by the Pi.

## Linux vcan

SocketCAN `vcan` is Linux-only. Use it when you want to validate the real SocketCAN adapter without physical CAN hardware.

Terminal 1:

```bash
./scripts/vcan_up.sh
uv run e87canbus-bench-pingpong --interface vcan0
```

Terminal 2:

```bash
uv run e87canbus-sim-neotrellis-socketcan --interface vcan0 --cycles 4
```

Bring `vcan0` down with:

```bash
./scripts/vcan_down.sh
```
