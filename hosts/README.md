# Linux host applications

This package installs the coordinator and the separate console host. The coordinator reads vehicle
CAN networks, owns desired steering and profile state, and serves the management API. The console
host serves the driver UI and reports bounded activity from a receive-only K-CAN connection.

## Controller path

CAN readers timestamp frames and submit them to a bounded inbox. HTTP commands use the same owner
thread. The kernel applies each input to immutable state and publishes complete browser projections
through SSE. Vehicle speed is telemetry; it cannot trigger a steering command. Network reader and
inbox faults remain health facts.

The coordinator stores desired steering mode, manual level, maximum override and the selected curve.
It neither drives nor observes Servotronic hardware. Button profiles retain assignments, colours,
animations and command active-state rules. There is no physical or simulated button input until the
independent button pad has its HTTP route.

## Deployment profiles

One profile selects the network transport, vehicle source and simulation API routes.

| | `car` | `bench` | `simulator` |
|---|---|---|---|
| CAN transport | SocketCAN | SocketCAN | in-memory |
| Vehicle | physical | emulated | emulated |
| Physical networks opened | all three | all three | none |
| Simulation API | absent | vehicle only | full |

Live composition creates receive endpoints only. Bench vehicle controls inject encoded synthetic
frames into the same decoder used by the simulator; they do not transmit on physical CAN. The car
profile cannot decode simulation-only IDs.

## Running

```bash
uv run e87canbus run --profile simulator
uv run e87canbus run --profile car
uv run e87canbus run --profile car --dry-run
uv run e87canbus-console
```

For the Pi, bring up the required SocketCAN interfaces at their configured bitrates before starting
the service. Follow the [deployment runbook](../deploy/README.md) for provisioning.

A fresh application database selects one `Default` button profile with sixteen empty slots. Existing
prototype databases must be replaced after the simplified coordinator slice. They are not migrated.

Steering curves contain eight fixed speed points with integer per-mille assistance values. Saving a
profile and selecting the active curve are separate HTTP operations. The browser can preview a curve,
but no coordinator calculation represents applied assistance. The selected curve and button profile
remain kernel-owned state and survive restarts through the application database.

## Checks

```bash
uv run pytest -q
uv run mypy
uv run ruff check hosts
uv run lint-imports
```

The coordinator and console OpenAPI documents are generated from their HTTP models. From `frontend`,
run `pnpm api:generate` after changing either contract and `pnpm api:check` to check for drift.
