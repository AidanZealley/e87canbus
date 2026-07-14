# Simulation

The in-process visual simulator is hardware-free, does not open CAN devices, and does not require
Linux.

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

The workbench exposes one in-memory `SimulationEngine` software component through REST plus a
WebSocket stream; “engine” here means the single-owner simulator runner, not a vehicle engine. A
bounded command queue serializes button actions, periodic control timers, and resets through one
owner task; an overloaded API request receives HTTP 503. Its `CoordinatorKernel` uses the same
decode, transition, commit, effect-execution, and TX-policy path as the live Pi runner. Simulated
devices emit frames onto the in-memory networks, and the engine timestamps those frames at receipt
before submitting them through the kernel's sole `dispatch` entry point.

Snapshots carry the kernel-owned revision, fatal-health status, and simulation session ID. Reset
starts a new session because trace sequence numbers restart at one; frame identity is therefore the
pair of session ID and sequence. Initial loads and resets carry the complete trace. Command
snapshots omit it and WebSocket frame events append only the new trace entries. Periodic timers
publish a snapshot only when that operation changes the public application, controller, or fatal
projection; refreshed external speed frames remain ordinary incremental trace events.
WebSocket sends, including the initial full snapshot, have a one-second default timeout. A stalled
or failed peer is removed while publication continues in order to the remaining peers; publication
is not detached from the owning operation.

A CAN or simulated-actuator output failure is fed back through the kernel after its originating
commit. The engine then commits and attempts shutdown once, publishes a fatal snapshot, and rejects
normal commands until reset. A failure during that final attempt is logged and discarded rather
than fed back or retried. If the ordinary shutdown effect initiated by reset fails, the stopped
session records and logs that fault; reset still replaces it and returns the new healthy session at
revision one. The replaced session's fault remains in logs rather than being copied into the new
session or a second diagnostic store.

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

Button `0` starts blue because the authoritative steering mode starts in Auto. Press it to send
`0x700 0001`; the application changes to Manual, replies with
`0x701 0400000000000000`, and the complete device state is replaced with button 0 amber and all
other positions off. Releasing sends `0x700 0000` but does not emit an LED snapshot because the
application remains in Manual. Pressing button `0` again changes the mode and LED back to Auto and
blue.

Buttons `1` and `2` enter Manual at the remembered runtime assistance level on their first press from Auto. Further presses decrease or increase the level within the configured bounds. Button `3` temporarily selects Manual at the maximum level and lights white; pressing it again restores the previous mode and manual level. Pressing `0` while maximum assistance is active disables it and selects Auto. Pressing `1` or `2` while maximum assistance is active returns to Manual at the saved level without adjusting it until the following press. This remembered state is not persisted across coordinator restarts.

Set a synthetic vehicle speed through `POST /api/vehicle/speed` with a body such as
`{"speed_kph": 42.5}`. The command operates the external simulated vehicle, which emits an extended
simulation-only CAN frame on the in-memory F-CAN. The engine timestamps and decodes that frame
through the kernel; the API does not inject `SpeedObserved` or application state. The live router
does not recognize the synthetic ID. The selected speed persists on the external vehicle. Immediately
before each queued control timer, the vehicle emits a fresh encoded frame and the engine drains it
through the kernel before dispatching the timer. `POST /api/vehicle/speed/silence` clears the
selection; subsequent timers emit no speed frame until another speed is set.

On each control timer, Auto maps fresh speed through the configured dimensionless `0.0..1.0`
assistance curve. Never-seen and stale speed select zero simulated assistance with distinct reasons.
Manual levels map evenly into the same range and maximum assistance selects `1.0`, including when
speed is absent. Fresh speed recovers Auto on the next control timer. CAN reader failure, inbox
overflow, and shutdown also select zero assistance with distinct reasons before the live loop exits.

The simulated steering controller is an executor capability rather than a K-CAN node because no
actuator wire protocol is known. The workbench displays its effective dimensionless simulation
projection, last accepted command reason, and watchdog state. Before any command is accepted, the
reason is explicitly absent and the workbench displays “No command accepted.” Its 250 ms watchdog
derives zero effective assistance when command refreshes stop while retaining the last accepted
command reason for diagnosis. These values are not measured feedback. Zero is only the simulator's
fallback; it is not a verified physical command or electrical safe state. Physical command
transport, range and polarity, valve response, feedback, controller topology, and watchdog behavior
remain unknown.

The current scheduled vehicle source, direct steering capability, and passive NeoTrellis LED sink
settle in one visible processing pass. Before the first simulated device is allowed to emit a CAN
response while processing an incoming CAN frame, `SimulationEngine` must regain a bounded
run-until-quiescent loop with an explicit livelock cap and deterministic tests. No unused cascade
loop is installed today.

## Safety Boundary

### Transmit safety

Coordinator transmission is denied by default. Each network must opt in with
`CanNetworkConfig.tx_enabled`; that composition choice creates a safe transmitter capability for the
effect executor. Every coordinator write is limited by `AppConfig.tx_policy`'s per-network bounded
window. The default limit is one coordinator-wide budget of 20 frames in any rolling second on each
enabled network, shared across arbitration IDs and independent of LED count. At a conservative 135
wire bits per standard-ID DLC-8 frame, the ceiling is at most 2.7% of 100 kbit/s K-CAN or 0.54% of a
500 kbit/s network before errors or retransmissions. It is a flood bound, not a target cadence. The
simulator explicitly grants K-CAN transmission and uses the same executor and policy path as the
live runtime: excess coordinator frames are logged and dropped without replay, while simulated
external devices remain unrestricted. A later accepted `0x701` snapshot replaces all 16 simulated
LED colours and repairs a missed intermediate state. The default live composition grants no
application transmission. Kernel or hardware listen-only mode is a separate deployment defense.

The simulator decodes the provisional project protocol on K-CAN:

- `0x700`: button-pad event.
- `0x701`: complete 16-colour coordinator LED snapshot.

The same IDs on PT-CAN or F-CAN are unknown traffic. `0x700` and `0x701` require collision
validation against a real K-CAN capture before any in-car transmission.

It does not simulate verified BMW vehicle control traffic. Its synthetic extended speed message is
defined only in `e87canbus.simulation.protocol`, is never installed in live composition, and is not
a candidate BMW ID. Placeholder BMW IDs remain notes only and must not be used as replay commands
until real captures, counters, and payload behavior have been verified. Future simulated inputs
must still pass through an external simulated node, encoded CAN frame, ingress timestamp, and
central decoder; no simulator API may inject domain events or coordinator state.
