# Simulation

This project has two hardware-free workflows:

- In-process simulation for macOS, Linux, and CI.
- Linux `vcan` simulation for validating the real SocketCAN adapter.

The in-process simulator is the default when you do not have hardware nearby. It does not open CAN devices and does not require Linux.

## In-Process Bench Simulation

Run:

```bash
uv run e87canbus-sim-bench
```

Run a fixed number of simulated button events:

```bash
uv run e87canbus-sim-bench --cycles 4
```

Use another simulated NeoTrellis button index:

```bash
uv run e87canbus-sim-bench --button-index 2
```

This simulates the current Arduino firmware behavior:

- Send project button-event frames on `0x700`.
- Alternate pressed and released states.
- Let the Pi bench app reply with LED-update frames on `0x701`.
- Record LED colours inside the simulated NeoTrellis node.

Expected logs alternate:

```text
sim neotrellis sent button event: index=0 pressed=True
received button event: index=0 pressed=True
sent led update: index=0 colour=green
sim neotrellis received led update: index=0 colour=2
```

## Visual Simulator Workbench

Run the FastAPI backend:

```bash
uv run e87canbus-sim-api
```

Run the browser frontend:

```bash
cd web
pnpm install
pnpm dev
```

Default URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

The workbench owns one in-memory simulator session and exposes it through REST plus a WebSocket stream. Click NeoTrellis button `0` to send `0x700 0001`; the Pi ping-pong handler replies with `0x701 0002`, and LED `0` turns green. Release or step again to send `0x700 0000`; the reply is `0x701 0000`, and LED `0` turns off.

## Linux vcan Simulation

SocketCAN and `vcan` are Linux-only. This workflow is useful on a Raspberry Pi or Linux laptop when you want to test the real `SocketCanBus` adapter without physical CAN hardware.

Bring up `vcan0`:

```bash
./scripts/vcan_up.sh
```

Terminal 1:

```bash
uv run e87canbus-bench-pingpong --interface vcan0
```

Terminal 2:

```bash
uv run e87canbus-sim-neotrellis-socketcan --interface vcan0 --cycles 4
```

Bring the virtual interface down:

```bash
./scripts/vcan_down.sh
```

Use a different interface name with `CAN_INTERFACE`:

```bash
CAN_INTERFACE=vcan1 ./scripts/vcan_up.sh
CAN_INTERFACE=vcan1 ./scripts/vcan_down.sh
```

## Safety Boundary

The simulator currently models only the private project protocol:

- `0x700`: Arduino/NeoTrellis button event.
- `0x701`: Pi LED update.

It does not simulate verified BMW vehicle control traffic. Placeholder BMW IDs remain notes only and must not be used as replay commands until real captures, counters, and payload behavior have been verified.
