# Coordinator

The coordinator is the central Python application deployed to the Raspberry Pi. It owns
authoritative application state and coordinates vehicle inputs, project devices, and the frontend.

## Source map

- `src/e87canbus/application/` — state, events, and application decisions. Start here when changing what the system does.
- `src/e87canbus/features/` — pure steering-assistance calculations.
- `src/e87canbus/protocol/` — CAN frame types plus encoding and decoding.
- `src/e87canbus/runtime.py` — single-owner kernel, ordered input values, commits, and diagnostics.
- `src/e87canbus/service.py` — bounded controller inbox, owner thread, timer and lifecycle.
- `src/e87canbus/composition.py` — validated live/simulated adapter presets and service factory.
- `src/e87canbus/live.py` — SocketCAN readers and the live runtime adapter.
- `src/e87canbus/adapters/` — integrations with real hardware or operating-system services.
- `src/e87canbus/simulation/` — in-memory CAN and virtual device implementations.
- `src/e87canbus/api/` — HTTP resources/commands and bounded Socket.IO live publication.
- `src/e87canbus/cli/` — executable entry points and bench utilities.
- `tests/` — tests arranged to mirror the source responsibilities.

The outer `coordinator/` directory names the deployable component. The inner `src/e87canbus/`
directory is the project-specific import namespace, following Python's conventional `src` layout.
This is why code imports `e87canbus.application` even though it is deployed as the coordinator.

## Steering curve profile contract

`features/steering.py` owns the immutable steering-curve definition and stored-profile metadata
values. Schema version 1 contains exactly eight explicit speed points at `0, 10, 20, 30, 60, 100,
160, and 250 km/h`. Authoritative values use integer tenths of km/h (`speed_deci_kph`) and integer
per-mille assistance (`assistance_per_mille`, `0..1000`) and requires assistance to be
non-increasing as speed rises. Curve definitions contain points only; the smooth evaluator uses
the checked-in Steffen/Hermite contract in the shared
[golden conformance vectors](../test-fixtures/steering/monotone-cubic-v1-vectors.json), including
endpoint hold, exact control-point values, binary64 tolerance and final `0..1` clamping. Python
and TypeScript load the same fixture.

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
closed unless redundant columns, canonical definition JSON and the stored fingerprint agree.

The unified API composes the profile and settings repositories over that shared database. Its
default path is `steering-profiles.sqlite3` in the process working directory;
`e87canbus run --mode simulated --profile-database PATH` (or
`E87CANBUS_PROFILE_DATABASE` for import-string deployment) selects a different file.
Startup applies migrations and seeding before accepting requests. Tests and other compositions can
inject the repositories independently.

The API accepts browser requests from the loopback Vite server on port 5173 by default. When an
isolated development frontend uses another port, pass its exact origin with repeatable
`--cors-origin`, for example `--cors-origin http://127.0.0.1:15173`. This remains an explicit
development allowlist; it does not broaden the deployment or authentication boundary.

`features/application_settings.py` owns the immutable speed/temperature unit preferences, canonical
Celsius thresholds and integer RPM shift thresholds. `/api/settings` returns the complete revisioned
document and replaces all editable fields with an expected-revision `PUT`. Successful commits
increment once, receive one canonical UTC timestamp and publish a precise `resources.changed`
event for `settings`; stale writers receive a typed `409`, while corrupt or unavailable
storage is a typed `503`. Theme remains browser-local and is absent from this contract.

`/api/steering/profiles` exposes list/create plus get/update/delete by profile ID. Create and update
accept one complete integer-unit definition; update and delete require `expected_revision`, with
delete carrying it as a query parameter. Responses contain the complete committed profile.
Saved profiles are activated by identity and expected revision through
`POST /api/commands/activate-steering-profile`; an unsaved editor draft uses the explicit
idempotent `PUT /api/commands/steering-curve` command. Maximum assistance and steering mode use
their corresponding `PUT /api/commands/*` set commands. Every command enters the bounded
controller service and returns only `accepted`, `boot_id` and the matched commit `revision`;
handlers never dispatch the kernel directly. The active curve is live operational state and is
published only in `controller.snapshot` and `steering.state`, not through an overlapping HTTP read
facade. Save and activation remain separate operations.

API failures use `{ "error": { "code", "message", ... } }`. Validation is `422`, missing profiles
are `404`, name/revision conflicts are `409`, and storage, timeout, unavailable adapter or
bounded-owner overload is `503`. Revision conflicts also return
`current_revision`. Successful saved CRUD publishes an exact `resources.changed` event
with resource ID and revision. Reconnecting clients receive the full
active curve in the normal authoritative snapshot and refetch the profile list, so no draft edits
or missed-event replay are required.

Socket.IO is mounted with FastAPI at `/socket.io` and uses one namespace. Every connection receives
`controller.snapshot`, containing protocol version 1, the opaque service `boot_id`, a monotonic
boot-scoped revision, fixed per-topic revisions and every current projection. Incremental server
events are `vehicle.state`, `engine.state`, `steering.state`, `buttons.state`, `devices.state`,
`controller.health`, `resources.changed`, and opt-in `trace.batch`. Only
`controller.resync`, `trace.subscribe`, and `trace.unsubscribe` are accepted from sockets; business
commands remain HTTP-only. Vehicle and engine values coalesce to 25 Hz, topic handoff retains one
latest unsent value, trace storage/batches and resource changes are bounded, and each Engine.IO
client has a finite 64-packet outbound queue. A client that fills that queue is disconnected and
counted as a transport saturation instead of blocking publication or losing arbitrary protocol
packets. No network client can block the controller owner or effect execution. Publisher and socket
shutdown share one two-second deadline and cancel all remaining publication tasks if it expires.
The generated contract is documented in
`protocol/README.md`. The repository frontend owns one Socket.IO connection outside the React tree.
There is no raw WebSocket or HTTP live-snapshot compatibility path.

Health publication is framework-independent and process-local. It reports readiness and fatal truth;
explicit network, device and steering faults; bounded inbox depth, capacity, current latency, warning
and overflow truth; persistence availability; and publisher running/fault state, failures,
trace/resource drops and slow-client queue saturations. Network availability and selected device
evidence remain in `devices.state` rather than being copied into health. Only the fixed trace ring
retains per-frame detail. Controller health is coalesced to one publication per second, while urgent
state topics keep their existing delivery behavior. A failed publisher records transport health
without notifying itself recursively. Persistence, readiness and decision-useful publisher changes
advance the service and health-topic revisions even when controller input is idle, so synchronized
clients do not discard them as stale.

The failure policy is explicit: a fatal reader, inbox overflow, CAN output or steering-actuator fault
enters the ordered safe shutdown path once; unknown output outcomes are never retried. Queue overflow
latches, rejects new commands and stops normal ingestion. Queue timestamps are retained and a
warning is logged when latency crosses into the configured warning state. Storage failure rejects
only the affected resource operation and does not rewrite already-loaded controller state. Emulator
failure becomes typed adapter health and
does not claim physical device behavior. Shutdown marks not-ready, stops ingress, commits the safe
request, drains only bounded work, stops publication, then closes adapters and short-lived database
resources. The complete owner/behavior table and recorded soak metrics are in
[`docs/reliability.md`](../docs/reliability.md).

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
bounded inbox; the controller owner thread alone dispatches kernel inputs and executes effects.
Queue latency is
logged without changing observation time.
Overflow, a repeatedly failing reader, or an effect I/O failure becomes visible kernel health and
ends the controller lifecycle. SocketCAN interfaces are closed independently so one shutdown error
cannot prevent later interfaces from closing.

The controller service owns one bounded inbox and dedicated owner thread in live and simulated
composition. It serializes button-device commands, persistent synthetic vehicle-speed selection and
silence, control timers, resets, kernel commits and ordered effects. Before each control timer, a
selected speed is re-emitted by the external vehicle and decoded through the kernel. The canonical
service projection supplies Socket.IO topic values including simulation session identity and the
ideal simulated controller's dimensionless assistance, optional last accepted command reason and
watchdog state. The service revision remains monotonic across simulation reset while the session
identity and trace sequence restart. An output fault terminates the session after one committed
shutdown attempt; normal
commands are rejected until reset creates a fresh kernel at revision one. A reset-time shutdown
fault is recorded on the stopped session and retained in logs while the canonical service and
Socket.IO projection report the new session. Socket.IO sends have a finite timeout, and every
Engine.IO client has a separate
finite packet capacity. The bounded publisher
is detached from the controller owner, so a stalled peer can delay only browser publication while
latest topic values replace older pending values; a saturated peer is then disconnected. Incremental
trace frames use the session ID with their reset-local sequence number.

The high-beam strobe is a separately scheduled simulator feature, not a BMW protocol claim.
Button `4` starts one bounded five-cycle flash-to-pass plan: 80 ms asserted and 80 ms deasserted
per cycle. Each transition produces a private synthetic extended K-CAN command to the virtual
vehicle, which exposes its observed high-beam state; those Pi-to-vehicle commands remain in the
normal simulated trace. The live composition has no high-beam actuator and the live
`ProtocolRouter` has no encoding or decoding for this frame, so enabling live K-CAN TX alone cannot
enable or transmit this output.

Every development action returns only `accepted` and the process `boot_id`. It does not report a
revision or session because later queued work may complete before the HTTP coroutine resumes. It
never returns or owns a parallel live snapshot; clients converge from Socket.IO state.

The same simulated vehicle can independently select or silence RPM, oil temperature and coolant
temperature. Each value uses its own unmistakably simulation-only extended PT-CAN frame adjacent
to the synthetic speed identifier, then follows normal ingress, routing, transition and live-state
publication. These identifiers are not BMW candidates and remain absent from `ProtocolRouter`.
RPM is canonical integer RPM; temperatures are canonical tenths of a degree Celsius. The
application retains observations internally but projects `null` with `never_observed` or `stale`
when no current value is usable. A separate `EngineTelemetryConfig` owns the one-second timeout,
and every active signal is re-emitted before each ordered control-timer evaluation.

Composition selects the repository-owned button pad as `physical`, `emulated`, `observer`, or
`disabled`, with exactly one source per role. Physical input is accepted only by live SocketCAN;
emulated input is accepted only from the virtual K-CAN device; observer cannot originate input;
disabled omits the capability. The projection separates controller-desired LEDs from
device-observed LEDs. The emulator may report connection and observation because it decodes the
actual output frame. A physical pad has no acknowledgement, so its connection and observed LEDs
remain unknown. No heartbeat or manually selected presentation-health state exists.

The provisional custom protocol is defined in `protocol/custom.toml`. Its generator owns the Python
wire constants, firmware header, and marked Markdown tables; `--check` and the test suite reject
single-artifact drift in IDs, lengths, byte positions, state values, or colour codes.
The coordinator derives exactly 16 desired LED colours, emits one `SetButtonLeds` effect, and packs
one `0x701` DLC-8 snapshot. The simulated button pad validates every nibble before replacing all 16
observed colours; invalid frames preserve the previous observation. There is one wire codec and no
simulator callback or alternate decoder.

## Running the unified controller

Bring up every enabled SocketCAN interface at its configured bitrate, then run:

```bash
uv run e87canbus run --mode live
```

The default live preset opens all three networks with application transmission disabled and exposes
the API after startup synchronization. It does
not claim SocketCAN kernel or hardware listen-only mode; configure that separately as an additional
deployment defense. K-CAN transmission is granted only by the isolated simulator and bench
compositions. Custom IDs `0x700` and `0x701` still require collision validation before any future
in-car transmission grant; see [the custom CAN ID registry](../protocol/custom_ids.md).

The simulated high-beam frame is not in that custom registry and is not a BMW candidate. Any future
live high-beam work requires named captures of stalk pull and release, verified counter/checksum and
message-cadence behavior, then controlled vehicle validation and a newly explicit live actuator
capability. It must not be enabled by changing a generic K-CAN transmit grant.

Run the development simulator with `uv run e87canbus run --mode simulated`. Simulator mutation
routes are registered only in simulated mode; live mode returns `404` for those development-only
paths. Both modes use the same HTTP/Socket.IO application composition. Use `--log-level` to change
logging verbosity.
Use `--button-pad-source emulated|observer|disabled` for simulated composition and
`--button-pad-source physical|observer|disabled` for live composition. The selection is fixed for
the process lifetime and invalid mode/source combinations fail before adapters start.
`uv run e87canbus run --mode live --dry-run` prints the selection without opening CAN interfaces.

Live mode defaults to loopback, serves an optional built `frontend/dist` with
`--frontend-directory`, registers no development mutation routes and enables no development CORS
origins. A non-loopback live bind is rejected because this API is unauthenticated. `/health/live`
proves the event loop responds and `/health/ready` proves the database and non-fatal controller are
ready. The canonical CLI observes a fatal owner stop and returns non-zero for supervised restart.
Install and operate it with the checked-in [systemd template](../deploy/README.md).

Software tests have proved the controller failure paths only against simulation and injected
adapters. Real steering failsafe work remains blocked until speed frames and the actuator boundary
are backed by named captures and hardware evidence. Placeholder candidate IDs remain non-executable.
