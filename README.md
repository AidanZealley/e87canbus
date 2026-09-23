# E87 CAN Bus

Hardware-aware, locally testable software for a track-only BMW E87 CAN bus project.

Current milestone: the hardware-independent coordinator kernel owns application state and is
exercised through the simulator's bounded, single-owner command path. A fresh database selects an
empty `Default` button profile. Backend simulation tests inject profiles to exercise button commands
that toggle steering mode, adjust manual assistance, and select maximum assistance. BMW CAN IDs, DSC
replay, Servotronic output, physical Trellis integration, and decoded in-car telemetry remain out of
scope.

The headless coordinator is configured for three isolated physical networks: K-CAN (`kcan`, 100 kbit/s),
PT-CAN (`ptcan`, 500 kbit/s), and F-CAN (`fcan`, 500 kbit/s). The Pi and simulated vehicle have an endpoint on all three. The coordinator currently sends no
CAN frames and produces no Servotronic output. The simulator does not forward traffic between
networks. A separate console Pi owns the driver screen,
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

Live readers timestamp CAN frames before placing them in a bounded inbox. One kernel owns desired
steering and profile state and applies pure transitions in input order. The simulator supplies
vehicle telemetry through CAN frames. Button profiles retain assignments, colours and animations,
but no physical or simulated button pad sends presses in this milestone.

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
telemetry controls remain in the toolbar. CAN topology and live trace are absent from the browser. The in-memory bus remains covered by backend tests.

See `docs/simulation.md` and
the [architecture decision index](docs/decisions/README.md).

## Verification

```bash
uv sync --locked
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

## Safety status

Live composition opens receive endpoints only and has no configured CAN transmitter or command
that can send a frame. Vehicle speed in the simulator crosses an encoded frame and the real
simulation decoder. Its extended CAN identifiers are simulation-only and have no BMW protocol
claim. The physical CAN IDs, DSC replay and Servotronic actuation still need capture and hardware
evidence.

The coordinator stores desired steering mode, manual level, maximum override and active curve.
It does not calculate or report applied assistance. Browser SSE publishes complete state and
replaces retained Zustand state on reconnection. Operational diagnostics report network reader,
inbox and persistence faults. The in-memory CAN trace remains an internal simulator tool.
