# Simulation

The in-process visual simulator is hardware-free, does not open CAN devices, and does not require
Linux.

## Visual Simulator Workbench

Run the FastAPI backend:

```bash
uv run e87canbus run --profile simulator --reload
```

The simulator profile includes a simulated vehicle and Servotronic peer. There is no simulated button pad until Slice 02 adds an HTTP client. Use the bench profile for physical CAN with simulated vehicle telemetry.

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
used by the SocketCAN profiles. A bounded controller inbox serializes periodic control timers,
and resets through one owner thread; an overloaded API request receives HTTP 503. Its
`CoordinatorKernel` uses the same
decode, transition, commit, effect-execution, and TX-policy path as the physical Pi profiles. Simulated
devices emit frames onto the in-memory networks, and the adapter timestamps those frames at receipt
before submitting them through the kernel's sole `dispatch` entry point.

The service projection carries boot-scoped revisions, fatal health and simulation session ID. Reset
starts a new session because trace sequence numbers restart at one; frame identity is therefore the
pair of session ID and sequence. Development controls return only `accepted` and the stable process
`boot_id`, never potentially stale revision/session metadata or a second live-state snapshot. The
repository frontend opens the generated coordinator `GET /api/live` SSE operation outside the
React tree. Each subscriber has bounded pending output, so a stalled peer cannot block the
controller owner, CAN input processing or effect execution. The first complete snapshot on every
connection is authoritative. Until it arrives, the frontend masks current live observations as
unavailable. HTTP failure, read failure, idle timeout and clean EOF reconnect to another snapshot.
The workbench badge distinguishes initial connection, synchronization, disconnection and
reconnection.

A CAN or simulated-actuator output failure is fed back through the kernel after its originating
commit. The simulated runtime then commits and attempts shutdown once, publishes fatal health, and rejects
normal commands until reset. A failure during that final attempt is logged and discarded rather
than fed back or retried. If the ordinary shutdown effect initiated by reset fails, the stopped
session records and logs that fault; reset still replaces it, and the canonical SSE projection
reports the new healthy session. The replaced session's fault remains
in logs rather than being copied into the new session or a second diagnostic store.

It models three independent CAN broadcast domains:

| Network | Interface | Bitrate | Nodes |
|---|---|---:|---|
| K-CAN | `kcan` | 100,000 | Pi, simulated vehicle, Servotronic emulator |
| PT-CAN | `ptcan` | 500,000 | Pi, simulated vehicle |
| F-CAN | `fcan` | 500,000 | Pi, simulated vehicle |

There is no automatic gateway behavior. Every emitted frame is retained in one chronological
2,000-entry trace, including unknown and peer-to-peer traffic. The browser does not subscribe to or
display this internal trace.

A fresh application database selects one protected `Default` button profile with sixteen
unassigned slots. The simulator therefore starts with no button action. Direct kernel tests can inject an authored profile to exercise press-to-intent routing. No physical or simulated pad produces presses during this slice. Profile CRUD and selection use the coordinator HTTP API; changes
to steering state continue through the HTTP controls. Existing prototype databases must be replaced
after the simplified-coordinator slice. They are not migrated.

Set a synthetic vehicle speed through `PUT /api/dev/simulation/vehicle/speed` with a body such as
`{"speed_kph": 42.5}`. The command operates the external simulated vehicle, which emits an extended
simulation-only CAN frame on the configured speed network (F-CAN by default). The runtime timestamps and decodes that frame
through the kernel; the API does not inject `SpeedObserved` or application state. The live router
does not recognize the synthetic ID. The selected speed persists on the external vehicle. Immediately
before each ordered control timer, the vehicle emits a fresh encoded frame and the runtime drains it
through the kernel before dispatching the timer.
`POST /api/dev/simulation/vehicle/speed/silence` clears the selection; subsequent timers emit no
speed frame until another speed is set.

`PUT /api/dev/simulation/vehicle/sweep` with `{"enabled": true}` starts a virtual-car-owned sweep
of speed, RPM, oil temperature, and coolant temperature. The source evaluates a continuous cosine
curve against monotonic simulator time on every 100 ms owner tick and emits all four CAN frames;
the browser sends only the mode change. Setting `enabled` to `false` holds the last values, while
an explicit set or silence command also ends the sweep and takes ownership of the selected signals.

The closed `bench` profile opens physical K-CAN, PT-CAN, and F-CAN, overrides synthetic speed to
K-CAN, and transmits each initial and refreshed speed frame onto physical `kcan`. Its transmit
grant remains K-CAN-only, so synthetic PT-CAN engine readings are decoded locally but are not put
on the physical bus. The more representative F-CAN speed default remains in the in-memory
simulator. Emission and decoding share one configuration value, so changing the network cannot
leave the simulator listening on the old bus. The production `car` profile never installs this
simulation-only protocol or grants transmission.

On each control timer, Auto maps fresh speed through the configured dimensionless `0.0..1.0`
assistance curve. Never-seen and stale speed select zero simulated assistance with distinct reasons.
Manual levels map from `0.0` through `1.0` in eleven stages at `0.1` increments and maximum assistance selects `1.0`, including when
speed is absent. Fresh speed recovers Auto on the next control timer. CAN reader failure, inbox
overflow, and shutdown also select zero assistance with distinct reasons before the live loop exits.

The simulated steering controller is an executor capability rather than a K-CAN node because no
actuator wire protocol is known. The driving console displays its effective dimensionless simulation
projection, last accepted command reason, and watchdog state. Before any command is accepted, the
reason is explicitly absent and the console displays “No command accepted.” Its 250 ms watchdog
derives zero effective assistance when command refreshes stop while retaining the last accepted
command reason for diagnosis. These values are not measured feedback. Zero is only the simulator's
fallback; it is not a verified physical command or electrical safe state. Physical command
transport, range and polarity, valve response, feedback, controller topology, and watchdog behavior
remain unknown.

The scheduled vehicle source and Servotronic peer settle in one visible processing pass. Before the first simulated device is allowed to emit a CAN
response while processing an incoming CAN frame, the simulated runtime adapter must gain a bounded
run-until-quiescent loop with an explicit livelock cap and deterministic tests. No unused cascade
loop is installed today.

## Safety Boundary

### Transmit safety

Coordinator transmission is denied by default. Each network must opt in with
`CanNetworkConfig.tx_enabled`; that composition choice creates a safe transmitter capability for the
effect executor. Every coordinator write is limited by `AppConfig.tx_policy`'s per-network bounded
window. The default limit is one coordinator-wide budget of 20 frames in any rolling second on each
enabled network, shared across arbitration IDs and independent of effect type. At a conservative 135
wire bits per standard-ID DLC-8 frame, the ceiling is at most 2.7% of 100 kbit/s K-CAN or 0.54% of a
500 kbit/s network before errors or retransmissions. It is a flood bound, not a target cadence. The
simulator explicitly grants K-CAN transmission and uses the same executor and policy path as the
live runtime: excess coordinator frames are logged and dropped without replay, while simulated
external devices remain unrestricted. The default live composition grants no
application transmission. Kernel or hardware listen-only mode is a separate deployment defense.

It does not simulate verified BMW vehicle control traffic. Its synthetic extended vehicle-observation messages are defined only in
`e87canbus.runners.simulation.protocol`, are never installed in live composition, and are not BMW
candidates. Placeholder BMW IDs remain notes only and must not be used as replay commands until real
captures, counters/checksums, payload behavior and cadence have been verified. Future simulated inputs must still pass through an external simulated node, encoded CAN
frame, ingress timestamp, and central decoder; no simulator API may inject domain events or
coordinator state.
