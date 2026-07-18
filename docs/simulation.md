# Simulation

The in-process visual simulator is hardware-free, does not open CAN devices, and does not require
Linux.

## Visual Simulator Workbench

Run the FastAPI backend:

```bash
uv run e87canbus run --profile simulator --reload
```

The simulator profile selects the emulated button pad, vehicle and Servotronic as one closed
composition. Use the `bench` profile when the Pi must use a physical button pad with only the
vehicle telemetry emulated.

Run the browser frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Default URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

The workbench selects one in-memory simulated runtime adapter behind the same `ControllerService`
used by the SocketCAN profiles. A bounded controller inbox serializes button actions, periodic control timers,
and resets through one owner thread; an overloaded API request receives HTTP 503. Its
`CoordinatorKernel` uses the same
decode, transition, commit, effect-execution, and TX-policy path as the physical Pi profiles. Simulated
devices emit frames onto the in-memory networks, and the adapter timestamps those frames at receipt
before submitting them through the kernel's sole `dispatch` entry point.

The service projection carries boot-scoped revisions, fatal health and simulation session ID. Reset
starts a new session because trace sequence numbers restart at one; frame identity is therefore the
pair of session ID and sequence. Development controls return only `accepted` and the stable process
`boot_id`, never potentially stale revision/session metadata or a second live-state snapshot. The
repository frontend uses one Socket.IO connection owned outside the React tree. Socket sends have a
one-second default timeout and Engine.IO client queues are finite. A stalled or failed peer can
delay only publication; it cannot block the controller owner, CAN input processing, or effect
execution. Socket.IO owns reconnect and Engine.IO heartbeat behavior. The first full
snapshot on every connection is authoritative, so a restarted backend can safely reset its session
and revision counters without stale browser state winning the merge. Until that snapshot arrives,
the frontend masks current live observations as unavailable. The workbench badge distinguishes
initial connection, synchronization, disconnection, and reconnection.

A CAN or simulated-actuator output failure is fed back through the kernel after its originating
commit. The simulated runtime then commits and attempts shutdown once, publishes fatal health, and rejects
normal commands until reset. A failure during that final attempt is logged and discarded rather
than fed back or retried. If the ordinary shutdown effect initiated by reset fails, the stopped
session records and logs that fault; reset still replaces it, and the canonical service/Socket.IO
projection reports the new healthy session at revision one. The replaced session's fault remains
in logs rather than being copied into the new session or a second diagnostic store.

It models three independent CAN broadcast domains:

| Network | Interface | Bitrate | Nodes |
|---|---|---:|---|
| K-CAN | `can0` | 100,000 | Pi, simulated vehicle, button-pad emulator |
| PT-CAN | `can1` | 500,000 | Pi, simulated vehicle |
| F-CAN | `can2` | 500,000 | Pi, simulated vehicle |

There is no automatic gateway behavior. Every emitted frame is retained in one chronological
2,000-entry trace, including unknown and peer-to-peer traffic. The network filters are frontend-only,
and reset's changed session identity clears the frontend trace while retaining topology configuration
and filter choices.

The default simulated composition selects the button pad's `emulated` role. The workbench labels
wire-level emulator exercise separately from semantic controller commands. Button `0` starts blue
because the authoritative steering mode starts in Auto. Press it to send
`0x700 0001`; the application changes to Manual, replies with
an ISO-TP RGB snapshot on `0x708`/`0x709`; after complete reassembly the simulated pad privately
applies button 0 amber and all other positions off. Releasing sends `0x700 0000` but does not emit an LED snapshot because the
application remains in Manual. Pressing button `0` again changes the mode and LED back to Auto and
blue.

`buttons.led_rgb` is controller-requested state and is what the browser renders. The simulated pad
independently receives and atomically reassembles the complete 48-byte RGB payload; this private
device state is exercised by tests but is not published as an observed-output API. A rate-limited
or malformed payload therefore never partially changes the device state.
Disabled mode has no emulator controls or device-originated traffic and omits the capability.
Source-mode changes require restart. Reset reconstructs the virtual topology and emulator, clears
trace identity and restores vehicle signals to never-observed without retaining old endpoints.

Buttons `1` and `2` enter Manual at the remembered runtime assistance level on their first press from Auto. Further presses decrease or increase the level within the configured bounds. Button `3` temporarily selects Manual at the maximum level and lights white; pressing it again restores the previous mode and manual level. Pressing `0` while maximum assistance is active disables it and selects Auto. Pressing `1` or `2` while maximum assistance is active returns to Manual at the saved level without adjusting it until the following press. This remembered state is not persisted across coordinator restarts.

Button `4` starts one bounded synthetic flash-to-pass sequence: five cycles of high beam asserted
for 80 ms and deasserted for 80 ms. It is ignored while a sequence is already active. The simulator
turns each phase into a private extended K-CAN command from the Pi to the virtual vehicle, so the
chronological trace shows the transmission and the lighting panel distinguishes requested from
observed virtual-car state. This is deliberately a virtual-car protocol only: it is neither a BMW
frame/ID nor a live vehicle command.

Set a synthetic vehicle speed through `PUT /api/dev/simulation/vehicle/speed` with a body such as
`{"speed_kph": 42.5}`. The command operates the external simulated vehicle, which emits an extended
simulation-only CAN frame on the in-memory F-CAN. The runtime timestamps and decodes that frame
through the kernel; the API does not inject `SpeedObserved` or application state. The live router
does not recognize the synthetic ID. The selected speed persists on the external vehicle. Immediately
before each ordered control timer, the vehicle emits a fresh encoded frame and the runtime drains it
through the kernel before dispatching the timer.
`POST /api/dev/simulation/vehicle/speed/silence` clears the selection; subsequent timers emit no
speed frame until another speed is set.

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

The current scheduled vehicle source, direct steering capability, and button-pad emulator
settle in one visible processing pass. Before the first simulated device is allowed to emit a CAN
response while processing an incoming CAN frame, the simulated runtime adapter must gain a bounded
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
external devices remain unrestricted. A later accepted ISO-TP RGB snapshot replaces all 16 simulated
LED values and repairs a missed intermediate state. The default live composition grants no
application transmission. Kernel or hardware listen-only mode is a separate deployment defense.

The high-beam strobe additionally requires its own simulator-only actuator capability. Live mode
does not construct that actuator and its router has no high-beam frame mapping; a future live K-CAN
grant therefore cannot enable this output accidentally. No BMW high-beam frame, live high-beam
actuator, or real-car TX capability exists in this repository.

The emulator uses the generated provisional project protocol on K-CAN; firmware compiles the same
transport but physical NeoTrellis RGB consumption remains deferred:

- `0x700`: button-pad event.
- `0x708`/`0x709`: bounded ISO-TP link carrying complete 16×RGB coordinator snapshots.

The same IDs on PT-CAN or F-CAN are unknown traffic. `0x700`, `0x708`, and `0x709` require collision
validation against a real K-CAN capture before any in-car transmission.

It does not simulate verified BMW vehicle control traffic. Its synthetic extended speed and
high-beam-command messages are defined only in `e87canbus.simulation.protocol`, are never installed
in live composition, and are not BMW candidates. Placeholder BMW IDs remain notes only and must not
be used as replay commands until real captures, counters/checksums, payload behavior and cadence
have been verified. Specifically, a real high-beam path needs named stalk-pull and stalk-release
captures plus controlled validation before a deliberately new live actuator capability could be
considered. Future simulated inputs must still pass through an external simulated node, encoded CAN
frame, ingress timestamp, and central decoder; no simulator API may inject domain events or
coordinator state.
