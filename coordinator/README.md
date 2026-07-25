# Coordinator

The Python application that runs on a Raspberry Pi in an E87 BMW. It reads the car's CAN
networks, drives a custom button pad and a Servotronic steering controller, and serves the
web UI. It owns the authoritative application state: everything else asks it or watches it.

The code layout is explained in the `e87canbus.domain` package docstring, which is the
best starting point for how the system is put together. This file covers what it does,
how to run it, and the boundaries that matter.

## The one idea worth knowing

Everything flows through a single mutation path, and nothing mutates state concurrently.

```
CAN frame ─┐
HTTP req  ─┼─▶ bounded inbox ─▶ ControllerLoop ─▶ kernel.dispatch(one input)
timer     ─┘   (one thread)                            │
                                                       ▼
                                       pure domain decides: next state + effects
                                                       │
                                                       ▼
                                     Commit ─▶ effects executed ─▶ CAN out
                                            └▶ snapshot published ─▶ Socket.IO
```

- The **domain** is pure. No I/O, no clock, no threads. Time is passed in as an argument.
- The **kernel** owns the state and is the only thing that changes it, one input at a time,
  in order. Unknown CAN traffic produces no commit at all.
- The **ControllerLoop** is the single thread allowed to call the kernel. That is why the
  kernel needs no locks. Web requests and CAN readers queue work; they never dispatch.
- **Effects are described, then performed.** The domain returns "send this frame" as a
  value; adapters carry it out after the commit lands. A failed effect is health, not a
  half-applied state change.

Practical consequence: to change behaviour, change a pure function and test it without a
car. To change *when* things happen, look at the loop and the runners.

## Deployment profiles

One flag picks the entire composition. Device sources, network access, transmit grants and
which API routes exist are fixed by the profile and cannot be recombined with other flags.

| | `car` | `bench` | `simulator` |
|---|---|---|---|
| CAN transport | SocketCAN | SocketCAN | in-memory |
| Button pad / Servotronic | physical | physical | emulated |
| Vehicle | physical | emulated | emulated |
| Networks opened | all three | K-CAN only | none |
| **Transmit granted** | **none** | K-CAN | K-CAN |
| Simulation API | absent (404) | vehicle only | full |

All three run the same HTTP and Socket.IO application. `car` transmits nothing: in-vehicle
CAN transmission stays denied until it is separately validated.

## Running it

```bash
uv run e87canbus run --profile simulator        # development, no hardware
uv run e87canbus run --profile car              # on the Pi
uv run e87canbus run --profile car --dry-run    # print the selection, open nothing
```

Bring up the SocketCAN interfaces the profile needs, at their configured bitrates, before
starting a SocketCAN profile. For the Pi, use the checked-in
[systemd template](../deploy/README.md).

Useful flags: `--profile-database PATH` (defaults to `steering-profiles.sqlite3` in the
working directory, or `E87CANBUS_PROFILE_DATABASE`), `--frontend-directory` to serve a
built frontend, `--cors-origin` to allow an extra dev origin, `--log-level`, `--host`,
`--port`.

`/health/live` proves the event loop responds. `/health/ready` proves the database is
migrated and the controller is not fatally faulted. A fatal controller stop exits non-zero
so a supervisor restarts it.

## Live state versus commands

The split is deliberate and absolute:

- **Socket.IO carries state, one namespace at `/socket.io`.** On connect a client gets
  `controller.snapshot` — the complete current projection, a boot ID and per-topic
  revisions. After that it gets incremental `vehicle.state`, `engine.state`,
  `steering.state`, `buttons.state`, `lighting.state`, `devices.state`,
  `controller.health`, `resources.changed` and opt-in `trace.batch`. Only resync and trace
  subscription are accepted *from* a socket.
- **HTTP carries commands.** Every command enters the bounded inbox and returns just
  `accepted`, `boot_id` and the commit `revision`. Handlers never touch the kernel directly.

No client can slow the controller. Publication is coalesced on a timer — telemetry at 25 Hz,
health at 1 Hz, trace at 10 Hz by default — each topic keeps only its latest unsent value,
and every client has a finite outbound queue. Fill it and you are disconnected and counted,
rather than blocking anyone else. Reconnecting clients get a full snapshot, so there is no
missed-event replay to reason about.

The wire contract is generated, not hand-written; see [`protocol/README.md`](../protocol/README.md).

## Durable state

SQLite, one file, standard-library driver. Ordered migrations run once inside an exclusive
transaction at startup, WAL journaling with `FULL` synchronous durability, and it fails
closed on a database newer than the code.

Everything user-editable — steering profiles, button profiles, application settings — is
**revisioned**. Writes carry the revision you expect to replace; if it moved, you get a
`409` with the current revision rather than silently clobbering. Rows are read back
defensively: redundant columns, canonical JSON and the stored fingerprint must agree or the
read fails.

Errors are typed and consistent: `422` validation, `404` missing, `409` conflict (name or
revision), `503` storage or overload. Successful writes publish a precise
`resources.changed` event carrying the resource ID and new revision.

## Steering curves

A curve is eight explicit speed points at 0, 10, 20, 30, 60, 100, 160 and 250 km/h. Values
are integers throughout — tenths of km/h and per-mille assistance (0–1000) — and assistance
must not increase with speed. Between points, a Steffen/Hermite evaluator is pinned by
[golden vectors](../test-fixtures/steering/monotone-cubic-v1-vectors.json) that Python and
TypeScript both load, so the browser preview and the car agree exactly.

A curve's identity is the SHA-256 of its canonical JSON — points and schema version only,
never its name or timestamps. The active curve is kernel-owned runtime state, not
configuration. Saving and activating are separate operations: activating a saved profile
goes by ID and expected revision, while an unsaved editor draft is pushed as an explicit
idempotent command.

## Button profiles

The pad has sixteen buttons. A profile says what each one does, as sixteen slots holding an
assignable command or nothing. Profiles are stored, revisioned and editable from the UI, and
the selected one survives restarts.

The set of assignable commands lives in exactly one place — `domain/buttons/catalogue.py`.
The storage codec, the HTTP schema and each button's idle LED colour are all derived from
it, so adding a command means adding a catalogue entry and an intent, then answering the
questions type-checking asks. LED colour follows what a button *does*, never which button
it is, so moving a command moves its colour with it.

Values whose legal range depends on the car — an assistance stage that this configuration
does not have — are rejected when the profile is saved, and degrade to a red feedback blink
if a profile stored before a configuration change is pressed.

## Safety boundaries

These are the constraints that stop a bug becoming a car problem. Treat them as load-bearing.

**Transmission is denied by absence, not by a flag.** There is no safe transmitter unless a
network is explicitly granted `tx_enabled`. The `car` profile grants none.

**Every granted write passes a rate ceiling.** By default 200 frames per rolling second per
network, shared across all arbitration IDs — a coordinator-wide flood budget, not a send
cadence. At a conservative 135 bits for a standard-ID DLC-8 frame that caps us at about
27 kbit/s: roughly 27% of a 100 kbit/s K-CAN and 5% of a 500 kbit/s network. A frame over
budget is dropped and logged, never queued, so state converges from the next complete
output instead of replaying a stale intermediate one.

**Nothing is bridged between networks automatically.** Any cross-network forwarding would
have to be written deliberately.

**The API is unauthenticated and binds to loopback.** A non-loopback bind is rejected for
SocketCAN profiles. Do not expose it until authentication, origin policy and an
editing-while-moving policy exist. The simulator is a development tool, not an
authorization boundary.

**The high-beam strobe is simulator-only.** It is a synthetic frame to a virtual car, not a
BMW protocol claim. The live router cannot encode or decode it, so granting live K-CAN
transmission cannot enable it. Making it real needs captures of stalk pull and release,
verified counter and checksum behaviour, vehicle validation, and a new explicit actuator
capability — never a widened generic grant.

**There is no verified speed decoder.** The simulator uses a synthetic one that live
composition never imports. Custom IDs `0x700`, `0x708` and `0x709` still need collision
validation before any in-car transmit grant; see the
[custom CAN ID registry](../protocol/custom_ids.md).

Failure paths have been proved against simulation and injected adapters only. Real steering
failsafe work stays blocked until speed frames and the actuator boundary have hardware
evidence behind them.

## When things go wrong

A fatal reader fault, inbox overflow, CAN output failure or steering-actuator fault enters
the ordered safe-shutdown path exactly once. Unknown output outcomes are never retried.
Overflow latches: new commands are rejected rather than queued indefinitely.

Failures are scoped to what actually failed. A storage error rejects that one operation and
leaves loaded controller state alone. An emulator failure is reported as emulator health and
never claims physical device behaviour.

Shutdown is ordered: mark not-ready, stop ingress, commit the safe request, drain only
bounded work, stop publishing, then close adapters and database handles. CAN interfaces
close independently so one failure cannot strand the others.

The full owner/behaviour table and soak metrics are in
[`docs/reliability.md`](../docs/reliability.md).

## Working on it

```bash
uv run pytest -q         # tests
uv run mypy              # types
uv run ruff check .      # lint
uv run lint-imports      # layering contracts — see pyproject.toml
```

The layering is enforced, not merely documented: `lint-imports` fails if the domain reaches
outward or the controller flow inverts.

Two contracts are generated and checked rather than maintained by hand — the CAN protocol
from `protocol/custom.toml`, and the OpenAPI and live-event schemas from the API models.
Both have a `--check` mode that CI runs, so a single-artifact drift in IDs, byte positions,
colour codes or request shapes fails the build. Regenerate rather than editing generated
files.
