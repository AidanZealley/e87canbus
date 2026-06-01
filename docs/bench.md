# Bench CAN Ping-Pong

This milestone validates Pi-to-Arduino CAN transport before any car wiring.

## Hardware Defaults

- Raspberry Pi 4 with Waveshare RS485 CAN HAT v2.1.
- HAT oscillator marking `12000`: use `oscillator=12000000`.
- Overlay interrupt: BCM `25`.
- Bench CAN bitrate: `500000`.
- Arduino Micro / ATmega32U4 with MCP2515 on CS pin `10`.
- Arduino MCP2515 firmware clock setting: `MCP_16MHZ`.

## Protocol

- Arduino sends button events on `0x700`: `[button_index, state]`.
- `state=0` means released; `state=1` means pressed.
- Pi replies with LED updates on `0x701`: `[button_index, colour]`.
- `colour=2` means green; `colour=0` means off.

## Run Locally On The Pi

```bash
sudo ./scripts/bench_can_up.sh
uv run e87canbus-bench-pingpong --interface can0
```

The expected Pi logs alternate:

```text
received button event: index=0 pressed=True
sent led update: index=0 colour=green
received button event: index=0 pressed=False
sent led update: index=0 colour=off
```

The expected Arduino serial logs alternate:

```text
sent button event index=0 state=pressed
received led update index=0 colour=2
sent button event index=0 state=released
received led update index=0 colour=0
```

Bring the bench CAN interface down with:

```bash
sudo ./scripts/bench_can_down.sh
```
