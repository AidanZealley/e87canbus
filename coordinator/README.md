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
projection. Version 1 accepts `linear-v1` and `monotone-cubic-v1` and requires assistance to be
non-increasing as speed rises. Linear profiles retain piecewise-linear behavior. The smooth
evaluator implements the checked-in Steffen/Hermite
[numerical contract](../docs/assist-curve/monotone-cubic-v1.md), including endpoint hold, exact
control-point values, binary64 tolerance and final `0..1` clamping. Python and TypeScript load the
same language-neutral golden vectors.

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
The kernel activation boundary also carries the consumer's explicit supported-interpolation set.
An unsupported definition is rejected before state or revision changes, and the API reports
`unsupported_interpolation` with the supported versions rather than substituting a linear curve.

`features/profile_repository.py` defines the persistence boundary and typed not-found, revision,
name-conflict and storage failures. `adapters/sqlite_profiles.py` implements it with the standard
library SQLite driver. `adapters/sqlite_database.py` owns the shared connection policy and ordered
schema migrations; composition initializes it once during API lifespan startup. Migration 1 retains
the steering catalog and stable profile seed exactly, while migration 2 adds the singleton
application-settings document. Initialization uses an exclusive transaction, enables WAL journaling
with `FULL` synchronous durability and fails closed on unsupported future versions. Operations use
short-lived connections and each mutation is one transaction. Lists are ordered by
case-insensitive name and profile ID, updates/deletes require an expected revision, and reads fail
closed unless redundant columns, canonical definition JSON and the stored fingerprint agree. The
live composition still has no profile-storage consumer and does not open the database.

The simulator API composes the profile and settings repositories over that shared database. Its
default path is `steering-profiles.sqlite3` in the process working directory;
`e87canbus-sim-api --profile-database PATH` (or `E87CANBUS_PROFILE_DATABASE` for import-string
deployment) selects a different file and remains compatible despite the file's expanded role.
Startup applies migrations and seeding before accepting requests. Tests and other compositions can
inject the repositories independently.

The API accepts browser requests from the loopback Vite server on port 5173 by default. When an
isolated development frontend uses another port, pass its exact origin with repeatable
`--cors-origin`, for example `--cors-origin http://127.0.0.1:15173`. This remains an explicit
development allowlist; it does not broaden the deployment or authentication boundary.

`features/application_settings.py` owns the immutable speed/temperature unit preferences, canonical
Celsius thresholds and integer RPM shift thresholds. `/api/settings` returns the complete revisioned
document and replaces all editable fields with an expected-revision `PUT`. Successful commits
increment once, receive one canonical UTC timestamp and publish
`application_settings_changed`; stale writers receive a typed `409`, while corrupt or unavailable
storage is a typed `503`. Theme remains browser-local and is absent from this contract.

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
`current_revision`; an interpolation capability conflict is `409` and returns
`supported_interpolations`. Successful saved CRUD publishes only a
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

The same simulated vehicle can independently select or silence RPM, oil temperature and coolant
temperature. Each value uses its own unmistakably simulation-only extended PT-CAN frame adjacent
to the synthetic speed identifier, then follows normal ingress, routing, transition and snapshot
publication. These identifiers are not BMW candidates and remain absent from `ProtocolRouter`.
RPM is canonical integer RPM; temperatures are canonical tenths of a degree Celsius. The
application retains observations internally but projects `null` with `never_observed` or `stale`
when no current value is usable. A separate `EngineTelemetryConfig` owns the one-second timeout,
and every active signal is re-emitted before each ordered control-timer evaluation.

Simulator snapshots also contain a complete, stable-order `devices` projection for the button pad
and steering controller. Both start online; the single-owner simulation queue can explicitly set
either to online, degraded or offline, and reset restores both online. Degraded and offline use the
stable `simulated_degraded` and `simulated_offline` reasons. These manually selected values are UI
test inputs only: they do not change CAN traffic, steering behavior, watchdog state, or establish
real device heartbeat and diagnostic criteria.

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
