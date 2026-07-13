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

The workbench exposes one in-memory simulation engine through REST plus a WebSocket stream. A
bounded command queue serializes button actions, periodic control timers, and resets through one
owner task; an overloaded API request receives HTTP 503. Its `CoordinatorKernel` uses the same
decode, transition, commit, effect-execution, and TX-policy path as the live Pi runner. Simulated
devices emit frames onto the in-memory networks, and the engine timestamps those frames at receipt
before submitting them through the kernel's sole `dispatch` entry point.

Snapshots carry the kernel-owned revision, fatal-health status, and simulation session ID. Reset
starts a new session because trace sequence numbers restart at one; frame identity is therefore the
pair of session ID and sequence. Initial loads and resets carry the complete trace. Command
snapshots omit it and WebSocket frame events append only the new trace entries. Periodic timers
publish a snapshot only when that operation changes the public application projection.

A CAN or simulated-actuator output failure is fed back through the kernel after its originating
commit. The engine then commits and attempts shutdown once, publishes a fatal snapshot, and rejects
normal commands until reset. A failure during that final attempt is not retried. Reset constructs a
healthy session whose new kernel starts at revision one.

It models three independent CAN broadcast domains:

| Network | Interface | Bitrate | Nodes |
|---|---|---:|---|
| K-CAN | `can0` | 100,000 | Pi, simulated vehicle, NeoTrellis |
| PT-CAN | `can1` | 500,000 | Pi, simulated vehicle |
| F-CAN | `can2` | 500,000 | Pi, simulated vehicle |

There is no automatic gateway behavior. Every emitted frame is retained in one chronological
2,000-entry trace, including unknown and peer-to-peer traffic. The network filters are frontend-only,
and reset's full empty snapshot clears the frontend trace while retaining topology configuration
and filter choices.

Button `0` starts blue because the authoritative steering mode starts in Auto. Press it to send `0x700 0001`; the application changes to Manual, replies with `0x701 0004`, and the button becomes amber. Releasing sends `0x700 0000` but does not clear the LED because the application remains in Manual. Pressing button `0` again changes the mode and LED back to Auto and blue.

Buttons `1` and `2` enter Manual at the remembered runtime assistance level on their first press from Auto. Further presses decrease or increase the level within the configured bounds. Button `3` temporarily selects Manual at the maximum level and lights white; pressing it again restores the previous mode and manual level. Pressing `1` or `2` while maximum assistance is active returns to Manual at the saved level without adjusting it until the following press. This remembered state is not persisted across coordinator restarts.

Set a synthetic vehicle speed through `POST /api/vehicle/speed` with a body such as
`{"speed_kph": 42.5}`. The command operates the external simulated vehicle, which emits an extended
simulation-only CAN frame on the in-memory F-CAN. The engine timestamps and decodes that frame
through the kernel; the API does not inject `SpeedObserved` or application state. The live router
does not recognize the synthetic ID.

On each control timer, Auto maps fresh speed through the configured dimensionless `0.0..1.0`
assistance curve. Never-seen or stale speed selects zero simulated assistance. Manual levels map
evenly into the same range and maximum assistance selects `1.0`, including when speed is absent.
Fresh speed recovers Auto on the next control timer. Reader failure, inbox overflow, and shutdown
also select zero assistance with a reason before the live loop exits.

The simulated steering controller is an executor capability rather than a K-CAN node because no
actuator wire protocol is known. Its 250 ms watchdog derives zero assistance when command refreshes
stop. Zero is only the simulator's fallback; it is not a verified physical command or electrical
safe state. Physical command transport, range and polarity, valve response, feedback, controller
topology, and watchdog behavior remain unknown.

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

### Transmit safety

Coordinator transmission is denied by default. Each network must opt in with
`CanNetworkConfig.tx_enabled`; that composition choice creates a safe transmitter capability for the
effect executor. Every coordinator write is limited by `AppConfig.tx_policy`'s per-network bounded
window. The simulator explicitly grants K-CAN transmission and uses the
same executor and policy path as the live runtime: excess coordinator frames are dropped, while
simulated external devices remain unrestricted. The default live composition grants no application
transmission. Kernel or hardware listen-only mode is a separate deployment defense.

The simulator decodes the provisional project protocol on K-CAN:

- `0x700`: button-pad event.
- `0x701`: coordinator LED update.

The same IDs on PT-CAN or F-CAN are unknown traffic. `0x700` and `0x701` require collision
validation against a real K-CAN capture before any in-car transmission.

It does not simulate verified BMW vehicle control traffic. Its synthetic extended speed message is
defined only in `e87canbus.simulation.protocol`, is never installed in live composition, and is not
a candidate BMW ID. Placeholder BMW IDs remain notes only and must not be used as replay commands
until real captures, counters, and payload behavior have been verified. Future simulated inputs
must still pass through an external simulated node, encoded CAN frame, ingress timestamp, and
central decoder; no simulator API may inject domain events or coordinator state.
