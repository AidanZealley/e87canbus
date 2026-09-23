# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: the hardware-independent coordinator kernel owns application state and is
exercised through the simulator's bounded, single-owner command path. A fresh database selects an
empty `Default` button profile. Backend simulation tests inject profiles to exercise button commands
that toggle steering mode, adjust manual assistance, and select maximum assistance. BMW CAN IDs, DSC
replay, Servotronic output, physical Trellis integration, and decoded in-car telemetry remain out of
scope.

The headless coordinator is configured for three isolated physical networks: K-CAN (`kcan`, 100 kbit/s),
PT-CAN (`ptcan`, 500 kbit/s), and F-CAN (`fcan`, 500 kbit/s). The Pi and simulated vehicle have an
endpoint on all three. The simulated Servotronic
controller is a direct actuator capability because no physical wire protocol is verified. The
simulator does not forward traffic between networks. A separate console Pi owns the driver screen,
its locally served frontend, and receive-only K-CAN observation. It reaches the coordinator over a
provisioned, non-routing Wi-Fi network with mutual TLS. Either host can fail without becoming the
other's control owner.

## Layout

- `hosts/` - role-neutral Linux host package, coordinator/console compositions, and tests.
- `devices/` - one independently buildable firmware project per physical device.
- `embedded-libs/` - repository-owned libraries shared by device firmware projects.
- `frontend/` - pnpm workspace containing separate coordinator and console Vite applications plus
  their UI-free coordinator client package.
- `protocol/` - cross-device CAN IDs, payload documentation, and BMW DBC notes.
- `docs/` - setup, wiring, decoded-message, architecture-decision, and remaining-work notes.
- `scripts/` - device upload and CAN helpers.
- `PROJECT_CONTEXT.md` - source project context.

The Python package uses the conventional `src` layout, with one architectural layer per
top-level folder (dependencies point inward: `api`/`cli`/runners → `service` → `kernel` →
`domain`). Start in `hosts/src/e87canbus/domain/` for system behaviour, `kernel/` for the
state machine, `service/` for the owner lifecycle, `protocol/` for CAN encoding, `adapters/` for
real hardware, `runners/` for the live/simulated compositions (including `runners/simulation/`
virtual hardware), and `api/` for the frontend interface.

Live readers timestamp CAN frames before placing them in a bounded inbox. One kernel owns immutable
application state and applies pure transitions in input order; committed effects leave through an
explicit CAN transmitter or actuator capability, with one network rate policy guarding CAN writes.
The simulator operates the vehicle and Servotronic peer through their existing CAN paths. Button
profiles still store assignments, colours and animations, but no physical or simulated button pad
sends presses during this milestone. Direct kernel inputs exercise the retained press-to-intent path.

## Raspberry Pi deployment

For blank coordinator and console Pi 4s, follow the
[provisioning runbook](deploy/README.md). It covers image builds, installation recovery, safe SD
writing, first boot and authenticated Wi-Fi. The electrical rationale for the coordinator's
combined Waveshare boards is recorded in the
[three-channel CAN stack design](docs/waveshare-three-channel-stack.md).

## Local Setup

```bash
uv sync
```

Run the dry-run CLI:

```bash
uv run e87canbus run --profile car --dry-run
```

Run the visual simulator workbench:

```bash
# Terminal 1
uv run e87canbus run --profile simulator --reload

# Terminal 2
uv run e87canbus-console --port 8001

# Terminal 3
cd frontend
pnpm install
pnpm dev
```

Default URLs:

- Coordinator backend/workbench: `http://127.0.0.1:8000` / `http://localhost:5173`
- Console backend/frontend: `http://127.0.0.1:8001` / `http://localhost:5174`

Process liveness is exposed at `/health/live`; `/health/ready` becomes successful only after the
database, controller and publisher have started and returns `503` on persistence or fatal controller
failure. The old placeholder `/api/health` route no longer exists.

The workbench contains the coordinator-panel simulator and button-profile editor. Simulated vehicle
telemetry controls remain in the toolbar. CAN topology, live trace and custom-CAN device controls
are intentionally absent from the browser. Their internal simulation behavior remains covered by
backend tests.

See `docs/simulation.md` and
the [architecture decision index](docs/decisions/README.md).

## Verification

```bash
uv sync --locked
uv run python scripts/generate_custom_protocol.py --check
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
bash -n scripts/*.sh deploy/bin/* deploy/kiosk/*.sh
uv run lint-imports
```

Run the frontend checks:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

## Safety Status

The default live composition disables application transmission on every CAN network. K-CAN transmission
is granted only by the isolated simulator and bench compositions, where coordinator output remains
rate-limited. This application-level RX-only default is separate from configuring SocketCAN or CAN
hardware in listen-only mode, which remains a recommended deployment defense. The coordinator has
no high-beam command or actuator, and its simulator has no high-beam frame. DSC replay and
capture-backed BMW high-beam commands are not implemented. A physical fan-bench Servotronic
controller now implements synthetic-speed reception, a compiled-in assistance curve, bounded PWM,
registration, and local failsafes. Closed-loop current regulation, rack-solenoid output hardware,
a real BMW speed decoder, and vehicle-safe Servotronic output remain intentionally unimplemented.
Vehicle-specific IDs and payloads must be captured and verified with `candump` before being treated
as confirmed. In particular, a future high-beam implementation needs named captures of stalk
pull and release, counter/checksum behavior and normal cadence, followed by controlled validation
before any live actuator can exist. The simulator's synthetic speed input is an explicitly
simulation-only extended CAN frame. It still travels from the simulated vehicle through ingress
timestamping, decoding, transition, commit, and effect execution; the live router cannot decode it.
Future verified vehicle inputs must replace synthetic definitions with captured network-specific
frames. There is no simulator-only state injection boundary.

The remaining bench-only Servotronic IDs are provisional and require collision checks against a
real K-CAN capture. Before any in-car connection, also verify K-CAN-compatible transceivers,
termination, the actual vehicle bitrate, firmware auto-transmit behavior, electrical isolation,
and grounding. The old button-pad firmware has been removed; no pad sends button presses or receives
coordinator feedback in this milestone.
The simulated Servotronic controller proves dimensionless target selection, stale/fault/shutdown
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

Setting speed through the toolbar's simulated-vehicle controls stores the selection on the external
simulated vehicle. It emits a fresh synthetic F-CAN frame before each control timer until explicitly
silenced. The driving console's steering screen
shows effective dimensionless simulated assistance, the last accepted command reason (or “No
command accepted”), and watchdog state; these are an ideal simulation projection, not measured
physical feedback. The coordinator and console host each publish a bounded SSE stream generated
from their own OpenAPI document. The console browser consumes both origins, while the coordinator
browser consumes only the coordinator stream. Complete snapshots replace retained Zustand state
after every connection. Development HTTP controls return acknowledgements and never duplicate
live state in response snapshots.

Operational diagnostics expose current bounded inbox depth, capacity, latency, warning and overflow
truth, explicit network, device and steering faults, and persistence availability. Each SSE
subscriber has bounded pending output and a slow subscriber is disconnected without blocking the
controller owner. The backend retains its CAN registry and bounded trace for simulation and
protocol tests; browser applications do not subscribe to or display either one. See the
[failure policy and soak evidence](docs/reliability.md) and
[Pi deployment and operation](deploy/README.md) for the loopback same-origin service, restart policy
and journal commands.
