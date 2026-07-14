# Coordinator

The coordinator is the central Python application deployed to the Raspberry Pi. It owns
authoritative application state and coordinates vehicle inputs, project devices, and the frontend.

## Source map

- `src/e87canbus/application/` — state, events, and application decisions. Start here when changing what the system does.
- `src/e87canbus/features/` — pure steering-assistance calculations.
- `src/e87canbus/protocol/` — CAN frame types plus encoding and decoding.
- `src/e87canbus/runtime.py` — single-owner kernel, ordered input values, commits, and diagnostics.
- `src/e87canbus/live.py` — threaded SocketCAN readers and the single-consumer live loop.
- `src/e87canbus/adapters/` — integrations with real hardware or operating-system services.
- `src/e87canbus/simulation/` — in-memory CAN and virtual device implementations.
- `src/e87canbus/api/` — HTTP and WebSocket interface used by the frontend.
- `src/e87canbus/cli/` — executable entry points and bench utilities.
- `tests/` — tests arranged to mirror the source responsibilities.

The outer `coordinator/` directory names the deployable component. The inner `src/e87canbus/`
directory is the project-specific import namespace, following Python's conventional `src` layout.
This is why code imports `e87canbus.application` even though it is deployed as the coordinator.

## Steering curve profile contract

`features/steering.py` owns the immutable steering-curve definition and stored-profile metadata
values. Schema version 1 contains exactly eight explicit speed points at `0, 10, 20, 30, 60, 100,
160, and 250 km/h`. Authoritative values use integer tenths of km/h (`speed_deci_kph`) and integer
per-mille assistance (`assistance_per_mille`, `0..1000`); float pairs exist only as a calculation
projection. Version 1 accepts `linear-v1` and requires assistance to be non-increasing as speed
rises. `monotone-cubic-v1` is reserved and fails validation until its later implementation phase.

Definition identity is the lowercase SHA-256 digest of compact, key-sorted UTF-8 JSON containing
only `schema_version`, `interpolation`, and the ordered integer point fields. Profile IDs, names,
revisions, and timestamps are excluded. Stored timestamps use UTC ISO 8601 with six fractional
digits and a trailing `Z` (for example, `2026-07-14T10:30:00.000000Z`). Profile validation and
fingerprinting are pure coordinator functions with no FastAPI or persistence dependency.

The active curve is an immutable kernel-owned runtime value, not part of `SteeringConfig`.
`ActiveSteeringCurve` carries the complete validated definition, fingerprint, runtime-local
activation revision and optional matching saved profile ID/revision. Startup composition selects
the built-in or a previously loaded saved definition before constructing the kernel; a new runtime
starts at activation revision 1, so an unsaved activation does not survive reconstruction.
`ActivateSteeringCurve` is the only ordered mutation path. A changed definition increments both the
kernel commit revision and activation revision and immediately recalculates output only when Auto
mode has a fresh speed sample. Identical definitions emit no steering command and retain the
activation revision, while a changed saved-profile association is still published as metadata.
Current in-process activation completes with status `active`; snapshots reserve `activating` and
`activation_failed` for a future asynchronous consumer without implementing controller transport.

`features/profile_repository.py` defines the persistence boundary and typed not-found, revision,
name-conflict and storage failures. `adapters/sqlite_profiles.py` implements it with the standard
library SQLite driver. Composition supplies the database path and explicitly calls `initialize()`;
module import has no filesystem side effect. Initialization applies numbered migrations under an
exclusive transaction, enables WAL journaling with `FULL` synchronous durability, and seeds the
stable profile ID `00000000-0000-4000-8000-000000000001` only when the catalog is empty. Operations
use short-lived connections and each mutation is one transaction. Lists are ordered by
case-insensitive name and profile ID, updates/deletes require an expected revision, and reads fail
closed unless redundant columns, canonical definition JSON and the stored fingerprint agree. The
live composition still has no profile-storage consumer and does not open the database.

The simulator API now composes that repository during FastAPI lifespan startup. Its default path is
`steering-profiles.sqlite3` in the process working directory; `e87canbus-sim-api
--profile-database PATH` (or `E87CANBUS_PROFILE_DATABASE` for import-string deployment) selects a
different file. Startup applies migrations and seeding before accepting requests. Tests and other
compositions inject their own temporary path or repository boundary.

`/api/steering/profiles` exposes list/create plus get/update/delete by profile ID. Create and update
accept one complete integer-unit definition; update and delete require `expected_revision`, with
delete carrying it as a query parameter. Responses contain the complete committed profile.
`/api/steering/curve-state` returns the authoritative active projection and its `/activate`
subresource accepts a complete definition with optional saved ID/revision provenance. Claimed
provenance is published only when the repository row has the same revision and definition.
Activation is enqueued with timers and simulated-device commands through the bounded simulation
owner; handlers never dispatch the kernel directly. Save and activation remain separate operations,
so saving cannot alter active state and applying cannot write a profile row.

API failures use `{ "error": { "code", "message", ... } }`. Validation is `422`, missing profiles
are `404`, name/revision/provenance conflicts are `409`, and storage or bounded-owner overload is
`503`; an immediate runtime effect failure after activation also returns typed `503` after the
owner publishes the committed active curve and fatal snapshot. Revision conflicts also return
`current_revision`. Successful saved CRUD publishes only a
`steering_profile_catalog_changed` WebSocket invalidation. Reconnecting clients receive the full
active curve in the normal authoritative snapshot and refetch the profile list, so no draft edits
or missed-event replay are required.

The simulator server defaults to loopback and permits the two local Vite development origins. It is
unauthenticated and is not an authorization boundary for an in-car writable deployment. Do not use
`--host` to expose it beyond loopback until authentication, origin policy, and editing-while-moving
policy have been defined separately from curve validation.

The kernel's `dispatch` method is the only application-state mutation path. Startup, received frames,
periodic timers, curve activations, reader and effect faults, inbox overflow, and shutdown enter that
ordered path. Timed inputs carry explicit observation times. Each decoded event runs through a pure
transition; the kernel commits the returned state and revision before the calling composition
executes the commit's ordered effects. Unknown CAN traffic creates no application commit. Reader,
CAN-effect, inbox-overflow, and steering-actuator faults update typed immutable diagnostics; the live
runner consumes fatal health and exits non-zero. Speed evaluation time cannot regress, so an older
timer or delayed frame cannot make stale data fresh. The simulator adds a synthetic speed decoder
that is not imported or enabled by live composition; no verified BMW speed decoder is configured.

The coordinator does not automatically forward frames between networks. Transmission is denied by
the absence of a safe transmitter capability and explicitly granted per network with `tx_enabled`.
Every granted write passes the holistic per-network window in `tx_policy`. Its default maximum of
20 frames in any rolling second is one coordinator-wide flood budget on each network, shared across
all arbitration IDs. Using a conservative upper bound of 135 wire bits for a standard-ID DLC-8
Classic CAN frame, that ceiling allocates at most 2,700 bit/s: 2.7% of 100 kbit/s K-CAN and 0.54% of
a 500 kbit/s network before errors or retransmissions. This is a safety ceiling rather than an
intended send cadence; it is not derived from LED count, startup output, or human timing. A dropped
frame is logged and discarded, not queued, so a later complete state converges without replaying an
intermediate output. Live reader threads only receive, timestamp, and enqueue into the configured
bounded inbox; the main thread alone dispatches kernel inputs and executes effects. Queue latency is
logged without changing observation time.
Overflow, a repeatedly failing reader, or an effect I/O failure becomes visible kernel health and
stops the runner with a non-zero result. SocketCAN interfaces are closed independently so one
shutdown error cannot prevent later interfaces from closing or mask an existing failure result.

The browser simulator has a separate bounded command queue. One asynchronous owner serializes
button-device commands, persistent synthetic vehicle-speed selection and silence, control timers,
resets, kernel commits, and WebSocket publication. Before each control timer, a selected speed is
re-emitted by the external vehicle and decoded through the kernel. Browser snapshots expose the
kernel-owned revision, simulation session ID, fatal-health status, and the ideal simulated
controller's effective dimensionless assistance, optional last accepted command reason, and
watchdog state. An output fault terminates the session after one committed shutdown attempt; normal
commands are rejected until reset creates a fresh kernel at revision one. A reset-time shutdown
fault is recorded on the stopped session and retained in logs while the reset response reports the
new healthy session. Initial and incremental WebSocket sends are bounded by the simulation send
timeout, and a stalled peer is removed without detaching or reordering publication. Incremental
trace frames use the session ID with their reset-local sequence number.

The provisional custom protocol is defined in `protocol/custom.toml`. Its generator owns the Python
wire constants, firmware header, and marked Markdown tables; `--check` and the test suite reject
single-artifact drift in IDs, lengths, byte positions, state values, or colour codes.
The coordinator derives exactly 16 logical LED colours, emits one `SetButtonLeds` effect, and packs
one `0x701` DLC-8 snapshot. The simulated button pad validates every nibble before replacing all 16
stored colours; there is one complete LED publication shape and no compatibility decoder.

## Running live

Bring up every enabled SocketCAN interface at its configured bitrate, then run:

```bash
uv run e87canbus
```

The default configuration opens all three networks with application transmission disabled. It does
not claim SocketCAN kernel or hardware listen-only mode; configure that separately as an additional
deployment defense. K-CAN transmission is granted only by the isolated simulator and bench
compositions. Custom IDs `0x700` and `0x701` still require collision validation before any future
in-car transmission grant; see [the custom CAN ID registry](../protocol/custom_ids.md). Use
`--log-level` to change logging verbosity. `uv run e87canbus --dry-run` prints the configuration
without opening CAN interfaces.

Phase 8 has proved the controller and failure paths against simulation-only speed and actuator
boundaries. Real steering failsafe work remains blocked until speed frames and the actuator boundary
are backed by named captures and hardware evidence. Placeholder candidate IDs remain non-executable.
