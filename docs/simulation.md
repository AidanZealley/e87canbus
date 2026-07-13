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

This simulates the current button-pad firmware behavior:

- Send project button-event frames on `0x700`.
- Alternate pressed and released states.
- Let the coordinator bench app reply with LED-update frames on `0x701`.
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
uv run e87canbus-sim-api --reload
```

Run the browser frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Default URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

The workbench owns one in-memory simulator session and exposes it through REST plus a WebSocket stream. The simulator routes button frames through the same hardware-independent application controller intended for the real Pi runtime.

Button `0` starts blue because the authoritative steering mode starts in Auto. Press it to send `0x700 0001`; the application changes to Manual, replies with `0x701 0004`, and the button becomes amber. Releasing sends `0x700 0000` but does not clear the LED because the application remains in Manual. Pressing button `0` again changes the mode and LED back to Auto and blue.

Buttons `1` and `2` enter Manual at the remembered runtime assistance level on their first press from Auto. Further presses decrease or increase the level within the configured bounds. Button `3` temporarily selects Manual at the maximum level and lights white; pressing it again restores the previous mode and manual level. This remembered state is not persisted across coordinator restarts.

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

- `0x700`: button-pad event.
- `0x701`: coordinator LED update.

It does not simulate verified BMW vehicle control traffic. Placeholder BMW IDs remain notes only and must not be used as replay commands until real captures, counters, and payload behavior have been verified.
