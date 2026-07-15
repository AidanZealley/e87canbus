# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: the hardware-independent coordinator kernel owns application state and is
exercised through the visual simulator's bounded, single-owner command path. NeoTrellis button `0`
toggles steering mode between Auto and Manual, buttons `1` and `2` select and adjust the remembered
manual level, and button `3` toggles a reversible maximum-assistance override. Together these
steering controls populate the full top row. BMW CAN IDs, DSC replay, high-beam strobe, Servotronic
output, physical Trellis integration, and the in-car touchscreen UI remain out of scope.

The coordinator is configured for three isolated physical networks: K-CAN (`can0`, 100 kbit/s),
PT-CAN (`can1`, 500 kbit/s), and F-CAN (`can2`, 500 kbit/s). The Pi and simulated vehicle have an
endpoint on all three, while the NeoTrellis attaches only to K-CAN. The simulated steering
controller is a direct actuator capability because no physical wire protocol is verified. The
simulator does not forward traffic between networks.

## Layout

- `coordinator/` - central Raspberry Pi application and its tests.
- `devices/` - one independently buildable firmware project per physical device.
- `frontend/` - React UI shared by the development simulator and future in-car display.
- `protocol/` - cross-device CAN IDs, payload documentation, and BMW DBC notes.
- `docs/` - setup, wiring, decoded-message, architecture-decision, and remaining-work notes.
- `scripts/` - device upload and CAN helpers.
- `PROJECT_CONTEXT.md` - source project context.

The Python package uses the conventional `src` layout. Start in
`coordinator/src/e87canbus/application/` for system behaviour, `features/` for feature
calculations, `protocol/` for CAN encoding, `adapters/` for real hardware, `simulation/` for
virtual hardware, and `api/` for the frontend interface.

Live readers timestamp CAN frames before placing them in a bounded inbox. One kernel owns immutable
application state and applies pure transitions in input order; committed effects leave through an
explicit CAN transmitter or actuator capability, with one network rate policy guarding CAN writes.
The simulator operates external nodes and follows that same path rather than injecting application
events or state. A button-pad LED decision is one complete 16-colour state, one effect, and one
provisional `0x701` DLC-8 frame; accepted frames replace the simulated device state atomically.

Each repository-owned button-pad composition selects exactly one `physical`, `emulated`,
`observer`, or `disabled` source. The workbench's emulator controls emit the generated `0x700` wire
message and are unavailable outside the emulated role. Dashboard operational controls use semantic
HTTP commands instead. Desired LEDs and observed emulator LEDs remain distinct; physical
observation is unknown because the protocol has no acknowledgement or heartbeat.

## Local Setup

```bash
uv sync
```

Run the dry-run CLI:

```bash
uv run e87canbus run --mode live --dry-run
```

Run the visual simulator workbench:

```bash
uv run e87canbus run --mode simulated --reload
cd frontend
pnpm install
pnpm dev
```

Default URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

Process liveness is exposed at `/health/live`; `/health/ready` becomes successful only after the
database, controller and publisher have started and returns `503` on persistence or fatal controller
failure. The old placeholder `/api/health` route no longer exists.

In the workbench, the topology panel shows all three networks and the chronological trace can be
filtered by network without another API request. Press NeoTrellis button `0` to toggle the
authoritative steering mode. Buttons `1` and `2` enter Manual at the last runtime manual level,
then decrement or increment within the configured bounds. Button `3` enters Manual at maximum
assistance and pressing it again restores the prior mode and manual level. Pressing `0` during the
maximum override disables it and selects Auto. Pressing `1` or `2` during the maximum override
instead returns to Manual at the saved level; the next press adjusts
it normally. The mode LED is blue for Auto or amber for Manual, while button `3` is white when its
override is active. Manual level memory is currently process-local and is reset on coordinator or
Pi restart.

Upload button-pad firmware from the host:

```bash
./scripts/button_pad_upload.sh
```

See `docs/simulation.md` and
the [architecture decision index](docs/decisions/README.md).

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh
```

Build the frontend:

```bash
cd frontend
pnpm build
```

Build the button-pad firmware:

```bash
cd devices/button-pad
pio run
```

## Safety Status

The default live composition disables application transmission on every CAN network. K-CAN transmission
is granted only by the isolated simulator and bench compositions, where coordinator output remains
rate-limited. This application-level RX-only default is separate from configuring SocketCAN or CAN
hardware in listen-only mode, which remains a recommended deployment defense. DSC replay,
high-beam K-CAN commands, and physical Servotronic output are intentionally not implemented yet.
Vehicle-specific IDs and payloads must be captured and verified with `candump` before being treated
as confirmed. The simulator's synthetic speed input is an explicitly simulation-only extended CAN
frame. It still travels from the simulated vehicle through ingress timestamping, decoding,
transition, commit, and effect execution; the live router cannot decode it. Future verified vehicle
inputs must replace synthetic definitions with captured network-specific frames. There is no
simulator-only state injection boundary.

The bench-only `0x700`/`0x701` IDs are provisional and require collision checks against a real
K-CAN capture. Before any in-car connection, also verify K-CAN-compatible transceivers, termination,
the actual vehicle bitrate, firmware auto-transmit behavior, electrical isolation, and grounding.
The current button-pad firmware transmits automatically and must not be connected to the car.
The simulated steering controller proves dimensionless target selection, stale/fault/shutdown
fallback, watchdog timeout behavior, and terminal handling of output faults. It does not establish
a physical command or electrical safe state. Command transport, range and polarity, valve response,
feedback, controller topology, and physical watchdog behavior remain unknown. Real steering
actuation remains gated on verified speed captures and actuator evidence, a verified safe state,
and a validated live grant; placeholder BMW IDs remain non-executable.

The default TX ceiling is a coordinator-wide flood bound on each explicitly enabled network: at
most 20 frames in any rolling second, shared by all arbitration IDs. A conservative 135 wire bits
for a standard-ID DLC-8 Classic CAN frame bounds that allocation at 2,700 bit/s: 2.7% of 100 kbit/s
K-CAN or 0.54% of a 500 kbit/s network before errors and retransmissions. It is a safety ceiling,
not an operating cadence or authority to transmit; it is independent of LED count and button timing.

In the workbench, setting speed stores the selection on the external simulated vehicle. It emits a
fresh synthetic F-CAN frame before each control timer until explicitly silenced. The steering panel
shows effective dimensionless simulated assistance, the last accepted command reason (or “No
command accepted”), and watchdog state; these are an ideal simulation projection, not measured
physical feedback. Socket.IO publication is bounded and latest-state coalesced; the frontend uses
one Socket.IO-to-Zustand path. The backend raw WebSocket remains external-consumer compatibility
until Phase 8 and has no repository-owned frontend consumer.

Operational diagnostics retain counters rather than event history: bounded inbox depth/capacity and
latency, per-network frame/effect outcomes, bounded publisher/coalescing/drop counts, active sockets,
trace subscribers and the fixed 2,000-row trace capacity. Controller health distinguishes CAN,
device, steering, persistence and UI transport faults. Publisher or client failure cannot block the
controller owner. See the [failure policy and soak evidence](docs/reliability.md) and
[Pi deployment and operation](deploy/README.md) for the loopback same-origin service, restart policy
and journal commands.
