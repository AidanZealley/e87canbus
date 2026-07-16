# Device registry implementation log

[Overview](README.md) · [Phase agent prompt](phase-agent-prompt.md)

This is the shared append-oriented record for the device-registry phases. Read
the complete log before starting a phase. After completing or blocking a
phase, update its status row and append an entry using the template below in
the same change as the implementation.

Do not rewrite earlier entries except to correct a factual error. Later agents
must be able to see the state, decisions, deviations, and verification handed
to them.

## Phase status

| Phase | Status | Completed by | Date | Verification |
|---|---|---|---|---|
| 1 | Completed | Codex lead after James/Gibbs workers | 2026-07-16 | Generated check; focused protocol/config/architecture tests (79 passed); full coordinator suite (516 passed) |
| 2 | Completed | Codex | 2026-07-16 | Focused Phase 2 suites (225 passed); full coordinator suite (524 passed); generated check, Ruff, mypy, compileall, and diff check passed |
| 3 | Completed | Codex lead after Tesla worker | 2026-07-16 | Required coordinator suites (41 passed); full coordinator suite (524 passed); frontend tests (30 unit + 60 component) and build passed; generated contract check, Ruff, mypy, and diff check passed |
| 4 | Completed | Codex lead after Sagan worker | 2026-07-16 | Phase 4 coordinator suites (119 passed); full coordinator suite (532 passed); frontend tests (30 unit + 63 component), build, lint, Ruff, mypy, compileall, and diff check passed |
| 5 | Completed | Codex lead after stalled Copernicus/Kuhn workers | 2026-07-16 | Default and overridden-ID PlatformIO builds passed; full coordinator suite (532 passed); frontend tests (30 unit + 63 component), build, lint, generated checks, Ruff, mypy, compileall, and diff check passed |

Allowed statuses are:

- Not started
- In progress
- Completed
- Blocked

A phase must not be recorded as completed while any required acceptance test
is failing or was not run. A blocked entry must identify the concrete blocker,
the checks already attempted, and the current repository state.

## Entries

### Phase 1 — Specification and protocol — 2026-07-16

- **Agent:** James (initial implementation), Gibbs (compatibility repair), and Codex lead audit
- **Final status:** Completed

#### Summary

Established the version 1 custom-device vocabulary and generated CAN protocol foundation. The
catalogue now contains one enabled, single-instance identity for `button_pad` and
`servotronic_controller`; `DeviceSource` is limited to physical, emulated, and disabled; and the
seven public registry lifecycle values are defined for later kernel work. The generator now owns
all eight project messages and produces synchronized Python, Arduino, and Markdown artifacts.
Strict HELLO, WELCOME_ACK, and HEARTBEAT payload codecs cover both role-specific ID families and
the exact overview vectors, including malformed-frame boundaries. The optional device directory
and active terminology were renamed to Servotronic, and stale observer-source callers were removed.

#### Important files changed

- `protocol/custom.toml` — sole source for protocol version, IDs, layouts, and values.
- `scripts/generate_custom_protocol.py` — generic message parsing and Python/header/Markdown generation.
- `coordinator/src/e87canbus/protocol/generated.py` — generated Python protocol constants.
- `devices/button-pad/include/can_ids.h` — generated firmware constants.
- `coordinator/src/e87canbus/protocol/can.py` — strict registry payload values and codecs.
- `coordinator/src/e87canbus/device.py` — static role, source, lifecycle, identity, and catalogue types.
- `coordinator/src/e87canbus/config.py` — generated custom CAN IDs with standard-ID and uniqueness validation.
- `devices/servotronic-controller/README.md` and repository documentation — consistent optional-device naming and deferred hardware boundaries.
- `coordinator/src/e87canbus/api/models/live.py` — keeps the current button-pad-only health projection type-safe until the phase 3 registry projection.
- `coordinator/tests/test_can_protocol.py`, `coordinator/tests/test_config.py`, and `coordinator/tests/test_generated_protocol.py` — vector, malformed-frame, catalogue, and artifact checks.

#### Public contract or schema changes

- Added generated `CUSTOM_DEVICE_PROTOCOL_VERSION = 1` and role-specific IDs `0x702`–`0x707`.
- Added typed `DeviceHelloPayload`, `DeviceWelcomeAckPayload`, and `DeviceHeartbeatPayload` codecs with DLC, field-width, reserved-byte, response-code, and standard-ID validation.
- Added `DeviceRole.SERVOTRONIC_CONTROLLER`, the reduced `DeviceSource` vocabulary, `DeviceLifecycleStatus`, immutable device identity/catalogue types, and the default two-role catalogue.
- Preserved the existing `0x700` button-event and `0x701` atomic LED snapshot payloads.

#### Verification

| Command | Result |
|---|---|
| `uv run python scripts/generate_custom_protocol.py --check` | Passed; generated artifacts current. |
| `uv run pytest coordinator/tests/test_generated_protocol.py coordinator/tests/test_can_protocol.py coordinator/tests/test_config.py coordinator/tests/test_architecture.py` | Passed; 79 tests. |
| `uv run pytest coordinator/tests` | Passed; 516 tests, 1 existing Starlette deprecation warning. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; 61 source files. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- One generic codec implementation is parameterized by the role-specific arbitration ID because both registry ID families have identical payload layouts.
- LED packing remains the only targeted generator metadata special case; all message IDs, fields, and values come from `protocol/custom.toml`.
- The pre-registry `DeviceProjection` remains temporarily for its current live/simulation consumers and is explicitly scheduled for removal in phase 3; no new public LED truth was added.
- The current live health adapter still publishes only its existing button-pad entry; its type boundary is kept explicit until phase 3 projects the complete registry role map.

#### Deviations from the phase document

- None.

#### Known limitations

- Runtime registry transitions, feature gating, live-contract migration, simulation peers, firmware behavior, live K-CAN acknowledgement authorization, collision validation, bench evidence, and physical readiness remain deferred to later phases or documented evidence gates.

#### Follow-up work

- Phase 2 must make the kernel the sole registry owner, consume these generated codecs/catalogue types, and implement lifecycle/timing and server-side gating without redeclaring protocol layouts.
- Remove the temporary `DeviceProjection` and migrate the live contract in phase 3.

---

## Entry template

Copy this section to the end of **Entries** and replace every placeholder.

```markdown
### Phase <number> — <title> — <YYYY-MM-DD>

- **Agent:** <identifier, name, or "not available">
- **Final status:** <Completed or Blocked>

#### Summary

<What was implemented and what user-visible/runtime result now exists.>

#### Important files changed

- `<path>` — <reason>

#### Public contract or schema changes

<List exact API, event, type, wire, configuration, or generated-artifact
changes. Write "None" when there were none.>

#### Verification

| Command | Result |
|---|---|
| `<exact command>` | <passed/failed/not run and relevant counts or error> |

#### Decisions and assumptions

- <Any implementation-level decision not already fixed by the phase document.>

#### Deviations from the phase document

- <Deviation and reason, or "None".>

#### Known limitations

- <Limitation, or "None beyond the documented deferred scope".>

#### Follow-up work

- <Specific work for later phases or physical validation.>
```

### Phase 2 — Kernel registry and gating — 2026-07-16

- **Agent:** Codex
- **Final status:** Completed

#### Summary

Implemented the Phase 2 controller-owned registry and symmetric CAN handshake. The kernel now
owns both configured device entries, validates role identity, protocol version, device/controller
sessions, and modulo-256 sequence ordering, emits role-specific `WELCOME_ACK` frames through the
normal typed effect and live TX-grant path, renews leases through the existing timer path, and
publishes device-topic changes only for public registry transitions. Simulation retains only the
Phase 2 kernel/executor compatibility path: tests and adapters may inject real encoded CAN frames
at the `ReceivedCanFrame` boundary, but the simulation runtime does not create or schedule virtual
registry peers and does not force lifecycle state.

Servotronic-dependent commands, decoded button actions, steering effects, and button LED effects
are gated at the kernel/server boundaries. Activation synchronizes the retained normal output once
after recovery, maximum assistance is cleared on optional-device loss, optional device and adapter
faults remain nonfatal, and origin-aware 500 ms red feedback is bounded by independent deadlines
without recursive feedback failures. Live composition retains explicit no-TX behavior by default;
simulation uses the same registry and TX policy paths.

#### Important files changed

- `coordinator/src/e87canbus/device_registry.py` — pure registry records, lifecycle transitions,
  lease expiry, session/sequence validation, and `feature_unavailable` domain exception.
- `coordinator/src/e87canbus/runtime.py` — sole registry owner, routing, ACK effects, timer and
  readiness gates, activation synchronization, maximum clearing, and origin propagation.
- `coordinator/src/e87canbus/protocol/router.py` and `coordinator/src/e87canbus/protocol/can.py`
  — typed registry observations and strict button-frame bounds using generated protocol values.
- `coordinator/src/e87canbus/output.py` — typed `EffectRequest`/`SendRegistryFrame` boundary,
  normal TX policy execution, and origin-preserving failures.
- `coordinator/src/e87canbus/application/events.py`, `application/state.py`, and
  `application/controller.py` — feedback events/deadlines, canonical LED overlays, and retained
  state clearing.
- `coordinator/src/e87canbus/live.py` and `coordinator/src/e87canbus/api/internal/commands.py`
  — live composition/gates and HTTP 409 mapping for unavailable operational work.
- `coordinator/src/e87canbus/simulation/devices.py`, `simulation/protocol.py`, and
  `simulation/runtime.py` — retained NeoTrellis/vehicle/actuator adapters, normal effect
  execution, and shared kernel gating; no virtual registry peer state machine was added.
- `coordinator/tests/registry_test_support.py` — one shared encoded-frame injector used only by
  device-dependent API, publication, and simulator tests.
- `coordinator/tests/test_device_registry.py` plus updated runtime, activation, command, profile,
  live, API, and simulation tests — lifecycle, gating, timing, encoded-frame injection, drop-policy,
  and regression coverage.

#### Public contract or schema changes

- Added kernel-visible `RegistryHelloObserved`, `RegistryHeartbeatObserved`,
  `DeviceRegistryEntry`, `SendRegistryFrame`, and `EffectRequest` values. Transport-bound effect
  values live in `output.py` so the inward-only application layer does not import protocol types.
- Added `ButtonCommandFailed` and `ButtonFeedbackDeadlineReached`, plus sixteen validated,
  non-public application feedback deadlines.
- Added `feature_unavailable` as the server-side 409 error code with dependency/status messages;
  profile repository CRUD remains independent of device availability.
- No generated protocol or schema artifacts changed; Phase 2 consumes the Phase 1 generator-owned
  codecs and IDs.

#### Verification

| Command | Result |
|---|---|
| `uv run pytest coordinator/tests/test_can_protocol.py coordinator/tests/test_runtime.py coordinator/tests/test_application_controller.py coordinator/tests/test_command_gateway.py coordinator/tests/test_output.py coordinator/tests/test_live.py coordinator/tests/test_reliability.py` | Passed; 99 tests, 1 existing Starlette deprecation warning. |
| `uv run pytest coordinator/tests/test_profile_api.py coordinator/tests/test_command_api.py coordinator/tests/test_live_publication.py coordinator/tests/test_simulator_api.py -q` | Passed; 73 tests, 1 existing Starlette deprecation warning. |
| `uv run pytest coordinator/tests/test_can_protocol.py coordinator/tests/test_runtime.py coordinator/tests/test_application_controller.py coordinator/tests/test_command_gateway.py coordinator/tests/test_output.py coordinator/tests/test_live.py coordinator/tests/test_reliability.py coordinator/tests/test_device_registry.py coordinator/tests/test_runtime_activation.py coordinator/tests/test_simulation_runtime.py coordinator/tests/test_live_publication.py coordinator/tests/test_simulator_api.py coordinator/tests/test_command_api.py coordinator/tests/test_profile_api.py -q` | Passed; 225 tests, 1 existing Starlette deprecation warning. |
| `uv run pytest coordinator/tests` | Passed; 524 tests, 1 existing Starlette deprecation warning. |
| `uv run python scripts/generate_custom_protocol.py --check` | Passed; generated protocol artifacts are current. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; no issues in 62 source files. |
| `uv run python -m compileall -q coordinator/src/e87canbus` | Passed. |
| `git diff --check` | Passed. |
| `git diff --stat` plus untracked-file audit | Passed; complete diff inspected after removing virtual-peer simulation work; no generated artifacts changed. |

#### Decisions and assumptions

- Public registry equality excludes private lease, sequence, registration, and controller-session
  fields. Duplicate valid heartbeats still receive ACKs but do not create a `devices` topic
  publication.
- A compatible HELLO enters `pending`; a matching healthy HEARTBEAT enters `active`; nonzero
  heartbeat status enters `fault`; ordinary lease expiry enters `stale`; unsupported protocol
  versions enter `incompatible` with the 15-second observation deadline; disabled sources remain
  disabled and ignore ingress.
- Button frames before active registration are ignored. Operational button actions and steering
  output are rejected or suppressed at the kernel regardless of frontend state, and suppressed
  effects are not replayed. Activation alone performs the complete retained-state synchronization.
- Profile repository CRUD remains independent of registry availability; only tests that exercise
  device-dependent activation or operational commands inject the minimal encoded frames needed.
- Live publication tests drain the complete initial topic publication set before injecting device
  frames or clearing emissions, keeping changed-topic and lighting assertions deterministic.
- Phase 2 simulation tests inject encoded HELLO and HEARTBEAT frames through the runtime's normal
  `ReceivedCanFrame` input boundary. They do not directly mutate registry entries or model peer
  heartbeat/ACK scheduling. Atomic LED snapshot/drop semantics are tested against the normal
  executor and observed NeoTrellis state without an unrelated heartbeat replay.
- The single-owner kernel remains authoritative; live and simulator adapter projections consume
  it and do not force registry lifecycle state.

#### Deviations from the phase document

- The transport-specific `SendRegistryFrame` and `EffectRequest` definitions are in
  `output.py`, rather than importing `RoutedCanFrame` into `application/events.py`. This is an
  intentional ownership boundary required by the existing architecture test: application code
  remains inward-only while the typed effect contract and normal TX executor remain intact.

#### Known limitations

- The temporary `DeviceProjection` and current live device projection remain until Phase 3's
  public registry-contract migration. No Phase 3 UI/API contract work was started.
- Virtual registry-peer state machines, heartbeat cadence/retry scheduling, simulator lifecycle
  controls, and peer-specific simulation coverage are intentionally not part of Phase 2. Phase 4
  owns that behavior; the current simulation tests cover only frame injection at the kernel
  boundary and the Phase 2 executor/gating contracts.
- Live K-CAN TX remains disabled unless explicitly granted. Physical readiness, collision
  validation, bench evidence, firmware handshake behavior, and in-car warnings remain deferred
  evidence/product work outside Phase 2.

#### Follow-up work

- Phase 3 may migrate the public live registry projection and remove the retained temporary
  `DeviceProjection` without moving registry ownership out of the kernel.
- Phase 4 must add the virtual peer state machines, scheduling, and simulator controls if required
  by its design; it should build on the Phase 2 kernel boundary rather than introducing a second
  registry owner. Later phases handle the separately documented UI, firmware, bench, and in-car
  readiness work.

### Phase 3 — Live contract and `/car` UI — 2026-07-16

- **Agent:** Tesla worker and Codex lead audit
- **Final status:** Completed

#### Summary

Migrated the live v1 contract from the temporary broad device projection to the fixed two-role
registry map. Servotronic actuator observation now belongs to `steering.servotronic`, while
`buttons.led_colours` is projected only from canonical controller application state. The `/car`
surface now hides disabled/not-found entries, retains observed lifecycle failures with specific
text and numeric fault codes, and explains unavailable steering and assistance dependencies.
Profile CRUD remains independent of device availability.

#### Important files changed

- `coordinator/src/e87canbus/service.py` and `coordinator/src/e87canbus/live.py` — expose kernel-owned
  registry/network state and Servotronic steering observation without adapter LED duplication.
- `coordinator/src/e87canbus/api/models/live.py` — define the fixed registry, steering, and health
  projections and canonical button LED mapping.
- `protocol/live-events-v1.schema.json` and `frontend/src/api/live-events.ts` — synchronize the
  generated JSON schema and explicit TypeScript transport types in unreleased protocol v1.
- `frontend/src/live/live-store.ts` — reconcile registry entries independently and preserve each
  unchanged role-entry reference; fixtures/tests cover no-render and no-replacement behavior.
- `frontend/src/components/car-overview/`, `car-steering-editor/`, and
  `device-status-footer/` — implement lifecycle filtering, dependency reasons, and unavailable
  dependent-screen states.

#### Public contract or schema changes

- Removed public `DeviceProjection`, `devices.devices`, `devices.steering_controller`,
  `desired_led_colours`, and `observed_led_colours` fields.
- Added `devices.registry.button_pad` and `devices.registry.servotronic_controller` with the
  fixed role/source/status/session/diagnostic fields.
- Added nullable `steering.servotronic`; health device entries now use `role` for both registry
  roles.
- Preserved live protocol version 1 and refreshed the generated schema and TypeScript contract.

#### Verification

| Command | Result |
|---|---|
| `uv run python scripts/generate_live_contract.py --check` | Passed; generated live schema current. |
| `uv run pytest coordinator/tests/test_live_contract.py coordinator/tests/test_live_publication.py coordinator/tests/test_socketio_server.py coordinator/tests/test_command_api.py coordinator/tests/test_profile_api.py` | Passed; 41 tests, 1 existing Starlette deprecation warning. |
| `uv run pytest coordinator/tests` | Passed; 524 tests, 1 existing Starlette deprecation warning. |
| `cd frontend && pnpm test -- --run` | Passed; 30 unit tests and 60 component tests across 17 files. |
| `cd frontend && pnpm build` | Passed; TypeScript project build and Vite production build. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; no issues in 62 source files. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- Live v1 is updated in place because the contract is unreleased; old frontend/backend combinations
  remain unsupported rather than gaining compatibility aliases.
- Registry state remains kernel-owned; live and simulator projections consume it. Phase 3 adds no
  virtual device state machines or simulator lifecycle controls.
- The optional Servotronic output adapter remains explicitly nullable, so an active registry entry
  alone does not make steering output usable.

#### Deviations from the phase document

- None.

#### Known limitations

- Virtual device peers, simulator lifecycle controls, and reusable `/dev` device cards remain
  deferred to Phase 4.
- Firmware handshake implementation, live physical CAN TX authorization, collision validation,
  bench/in-car evidence, and physical NeoTrellis/Servotronic validation remain deferred evidence
  gates for later phases and hardware work.

#### Follow-up work

- Phase 4 must consume the live registry entries for virtual peers and `/dev` controls without
  introducing another production registry owner or changing the v1 live contract.

### Phase 4 — Simulation and `/dev` UI — 2026-07-16

- **Agent:** Sagan worker and Codex lead audit
- **Final status:** Completed

#### Summary

Added virtual button-pad and Servotronic peers that exercise the real generated CAN registry
frames through independent in-memory K-CAN endpoints. HELLO, controller acknowledgements, and
heartbeat contact now run through a bounded fake-clock fixed-point drain; peer-local session,
sequence, protocol, status, contact, incompatibility, fault, and controller-loss behavior remain
separate from kernel-owned registry lifecycle state. Simulation reset starts both peers healthy and
the lifecycle actions operate by changing peer behavior rather than mutating registry entries.

Added strict development routes for connect, disconnect, reboot, protocol version, and status code,
including catalogue-role validation, byte bounds, idempotent connect/disconnect, and the required
absent-peer reboot conflict. The Servotronic peer is associated with the existing in-process
actuator model, while no physical Servotronic transport was introduced.

The `/dev` workbench now uses one reusable `SimulatedDeviceCard` around the NeoTrellis and
Servotronic panels. Cards display server registry status and diagnostics, expose context-sensitive
peer actions, and surface pending/error state without creating a browser-side lifecycle model.

#### Important files changed

- `coordinator/src/e87canbus/simulation/devices.py` — shared virtual peer state machine, role-specific
  IDs, frame codecs, contact timers, peer ACK processing, and Servotronic actuator peer.
- `coordinator/src/e87canbus/simulation/runtime.py` — peer endpoints, deterministic bounded drain,
  lifecycle command objects, session reset, and registry/trace projection integration.
- `coordinator/src/e87canbus/api/models/simulation.py` and
  `coordinator/src/e87canbus/api/routes/simulation.py` — strict development request bodies/routes.
- `coordinator/src/e87canbus/service.py` and `api/internal/commands.py` — shared unavailable-peer
  error boundary that preserves the architecture import rule and maps to HTTP 409.
- `frontend/src/components/simulator-workbench/components/simulated-device-card/` — reusable
  registry-driven card and action availability helper; `SimulatorNeoTrellis.tsx` and
  `SimulatorServotronic.tsx` consume it without nested duplicate cards.
- `coordinator/tests/test_simulation_runtime.py`, `test_simulator_api.py`, and the focused frontend
  card test — lifecycle traces, strict API boundaries, reset/recovery, and card behavior.

#### Public contract or schema changes

- Added development-only endpoints:
  `/api/dev/simulation/devices/{role}/connect`, `disconnect`, `reboot`,
  `protocol-version`, and `status-code`.
- Added strict `{protocol_version}` and `{status_code}` request models bounded to unsigned bytes;
  role path values are limited to `button_pad` and `servotronic_controller`.
- No live protocol v1, production registry schema, physical transport, or compiled firmware path
  was changed.

#### Verification

| Command | Result |
|---|---|
| `uv run pytest coordinator/tests/test_simulation_devices.py coordinator/tests/test_simulation_runtime.py coordinator/tests/test_simulator_api.py coordinator/tests/test_simulation_protocol.py coordinator/tests/test_simulation_bus.py` | Passed; 119 tests, 1 existing Starlette deprecation warning. |
| `uv run pytest coordinator/tests` | Passed; 532 tests, 1 existing Starlette deprecation warning. |
| `cd frontend && pnpm test -- --run` | Passed; 30 unit tests and 63 component tests across 18 files. |
| `cd frontend && pnpm build` | Passed; TypeScript project build and Vite production build. |
| `cd frontend && pnpm lint` | Passed. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; no issues in 62 source files. |
| `uv run python -m compileall -q coordinator/src/e87canbus` | Passed. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- The fixed-point scheduler is bounded to 32 virtual-device iterations and 256 controller-bus
  frames per execution; exceeding either bound raises an explicit runtime error instead of looping.
- A peer that is connected but has lost controller contact can be explicitly reconnected to create a
  new session; healthy repeated Connect/Disconnect actions remain idempotent.
- `SimulationDeviceUnavailable` lives at the service error boundary so the shared command adapter
  does not import simulation modules and the architecture ownership rule remains intact.
- The UI derives action availability from the server registry entry and synchronized transport; it
  does not infer or assign lifecycle transitions.

#### Deviations from the phase document

- None.

#### Known limitations

- The button-pad firmware now mirrors the generated vectors, role IDs, session/sequence rules,
  status handling, and timing in the real device; actual EEPROM and CAN behavior remain untested
  on hardware.
- Physical Servotronic output, compiled Arduino execution in simulation, CAN collision validation,
  live TX authorization, bench/in-car evidence, and physical hardware validation remain deferred.

#### Follow-up work

- Future hardware work must validate the button-pad firmware against the physical NeoTrellis and
  the same generated protocol vectors without claiming physical output readiness from compilation.

### Phase 5 — Button-pad firmware — 2026-07-16

- **Agent:** Copernicus and Kuhn workers stalled before making changes; Codex lead implemented and
  audited the phase fallback
- **Final status:** Completed

#### Summary

Implemented the button-pad side of the generated v1 registry handshake in the existing Arduino
Micro/MCP2515 project. The build fixes the role-specific stable ID to `DEVICE_ID=1` by default,
checks the unsigned 16-bit range at compile time, and allows a separately supplied build flag to
override the identity. EEPROM stores a 16-bit boot counter; startup reads it twice, increments it
with intentional modulo-65536 wrap, writes it, and verifies the stored result before discovery.

The firmware now uses explicit BOOTING, DISCOVERING, OPERATIONAL, CONTROLLER_LOST, INCOMPATIBLE,
and LOCAL_FAULT states with separate logical DISCOVERING, NORMAL, and ERROR display modes. HELLO
and heartbeat frames are assembled from generated offsets, use wrap-safe `millis()` scheduling
with bounded jitter, validate role-specific WELCOME_ACK identity/session/sequence/version/response,
and renew the controller lease only from matching acknowledgements. LED snapshots and future
button events are both gated by operational state and a fresh controller lease; validate-then-commit
LED decoding is retained and the old fake periodic press/release loop is removed.

#### Important files changed

- `devices/button-pad/platformio.ini` — Arduino EEPROM dependency and default `DEVICE_ID=1` build
  flag.
- `devices/button-pad/src/main.cpp` — EEPROM session persistence, generated CAN codecs, nonblocking
  device state machine, controller lease, logical display modes, gated LED/button behavior, and
  bounded diagnostics.
- `devices/button-pad/README.md` and `devices/README.md` — firmware behavior and explicit
  bench/physical-readiness boundaries.

#### Public contract or schema changes

- No protocol schema or generated artifact changed; `devices/button-pad/include/can_ids.h` remains
  generated from `protocol/custom.toml`.
- The firmware now implements the existing button-pad HELLO (`0x702`), WELCOME_ACK (`0x703`),
  HEARTBEAT (`0x704`), button event (`0x700`), and LED snapshot (`0x701`) contract.

#### Verification

| Command | Result |
|---|---|
| `pio run --project-dir devices/button-pad` | Passed; Arduino Micro firmware compiled and linked with generated v1 constants. |
| `PLATFORMIO_BUILD_FLAGS='-DDEVICE_ID=2' pio run --project-dir devices/button-pad` | Passed; explicit alternate stable-ID build compiled and linked. PlatformIO reports the expected duplicate-definition warning because the checked-in default flag remains present. |
| `uv run python scripts/generate_custom_protocol.py --check` | Passed. |
| `uv run python scripts/generate_live_contract.py --check` | Passed. |
| `uv run pytest coordinator/tests` | Passed; 532 tests, 1 existing Starlette deprecation warning. |
| `cd frontend && pnpm test -- --run` | Passed; 30 unit tests and 63 component tests across 18 files. |
| `cd frontend && pnpm build` | Passed; TypeScript project and Vite production build. |
| `cd frontend && pnpm lint` | Passed. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; no issues in 62 source files. |
| `uv run python -m compileall -q coordinator/src/e87canbus` | Passed. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- The AVR EEPROM API does not expose a read/write error result, so the firmware performs repeated
  reads and a post-write readback verification; any detected inconsistency enters LOCAL_FAULT.
- `uint16_t` session wrap is valid, including zero; no sentinel value is reserved by the protocol.
- CAN send failures are logged and retried at the next scheduled cadence. A failure during normal
  operation reports a nonzero local status through subsequent heartbeats.
- No physical rendering, topology, brightness, current-limit, collision, or readiness behavior was
  added; logical display modes are the only display interface in this phase.

#### Deviations from the phase document

- The delegated Copernicus and replacement Kuhn workers stalled without changing the worktree;
  the lead implemented the documented fallback after closing both workers. No scope or protocol
  deviation resulted.

#### Known limitations and remaining physical evidence gates

- Physical NeoTrellis scanning, logical-to-physical mapping, rendering, brightness, current limits,
  EEPROM wear/persistence, MCP2515 wiring, transceiver behavior, and bench execution remain
  unverified.
- CAN collision capture, live K-CAN TX authorization, vehicle/in-car testing, and physical
  button-pad integration remain prohibited/deferred.
- Servotronic firmware and physical Servotronic output remain out of scope.

#### Follow-up work

- Run isolated hardware bench validation, then record NeoTrellis rendering and K-CAN collision
  evidence before any live or in-car transmission is authorized.

### Completed implementation audit and repair — 2026-07-16

- **Agent:** Codex
- **Final status:** Completed

#### Summary

Audited the complete five-phase implementation against `main` and the authoritative handshake
specification. All seven reported findings were confirmed and repaired. Servotronic actuator
execution failures now remain inside the optional output-adapter health boundary, leave controller
readiness nonfatal, clear temporary maximum assistance, suppress further Servotronic output, and
reject later operational changes as `feature_unavailable` until the adapter is replaced or the
simulation is reset. Controller boot sessions now start from a random nonzero 16-bit seed and
advance without repetition within the process, so a process restart no longer deterministically
returns session `1`.

Firmware local-fault contact now expires through `CONTROLLER_LOST`, resumes HELLO discovery, and
returns to `LOCAL_FAULT` after rediscovery while continuing nonzero-status heartbeats. The virtual
button pad now accepts button events and LED snapshots only while operational with a fresh
controller lease. Simulation also sends the required first heartbeat immediately after an accepted
WELCOME acknowledgement.

The executor's raw-effect test compatibility path and the configurable catalogue-validation path
were removed. Registry entries retain the supported version selected from the one static catalogue,
whose protocol version now comes from the generated protocol constant. The default firmware
identity remains `1` in checked-in source, while explicit compiler overrides no longer redefine a
project build flag.

#### Findings confirmed

- Servotronic actuator failures incorrectly made global health fatal and stopped simulation.
- Firmware `LOCAL_FAULT` did not expire the controller lease or resume discovery.
- Controller sessions restarted deterministically from `1` in every process.
- The simulated button pad bypassed operational-state and controller-lease gates.
- `EffectExecutor` accepted raw `OutputEffect` values only for test convenience.
- Registry construction exposed an unused configurable catalogue and re-read protocol versions
  from the default catalogue instead of the installed entry.
- The overridden `DEVICE_ID` build produced macro-redefinition warnings.

#### Additional findings discovered

- Simulated peers waited one heartbeat cadence after WELCOME instead of sending the first heartbeat
  immediately.
- Firmware rediscovery with a retained nonzero local status incorrectly selected `OPERATIONAL`
  rather than returning to `LOCAL_FAULT`.
- Button-event and LED-snapshot codecs accepted extended frames carrying the numeric standard IDs.
- Several tests encoded the incorrect fatal optional-adapter behavior and brittle intermediate
  revision counts rather than the specified health and lifecycle boundaries.

#### Important files changed

- `coordinator/src/e87canbus/runtime.py` — nonfatal Servotronic actuator health, output gating,
  maximum-assistance clearing, and randomized nonzero boot-session seed.
- `coordinator/src/e87canbus/simulation/runtime.py` — stop simulation only for genuinely fatal
  execution failures.
- `coordinator/src/e87canbus/simulation/devices.py` — immediate first heartbeat and fresh-lease
  gating for simulated button and LED traffic.
- `coordinator/src/e87canbus/output.py` — one canonical `EffectRequest` executor interface.
- `coordinator/src/e87canbus/device.py` and `device_registry.py` — fixed static catalogue ownership
  and generated protocol-version use.
- `coordinator/src/e87canbus/protocol/can.py` — reject extended button-event and LED-snapshot
  frames on the standard-ID protocol.
- `devices/button-pad/src/main.cpp` — local-fault lease expiry, controller-loss rediscovery, and
  fault-preserving recovery.
- `devices/button-pad/platformio.ini` and `README.md` — warning-free build-time identity override.
- Coordinator tests for registry, runtime health, output execution, protocol validation,
  simulation, APIs, publication, profiles, and firmware-source regressions.

#### Tests added or corrected

- Added a subprocess regression proving controller sessions no longer reset deterministically
  across process starts and a same-process non-repetition assertion.
- Added focused nonfatal actuator-failure tests covering health, readiness, API behavior, output
  suppression, continued scheduling, shutdown, and reset.
- Added protocol-driven simulated NeoTrellis activation helpers and tests for pre-registration and
  expired-lease button/LED rejection.
- Added firmware-source regressions for local-fault controller-loss recovery and preservation of
  local-fault state after rediscovery.
- Added standard-versus-extended frame validation coverage for button and LED codecs.
- Corrected simulator handshake tests to assert the immediate first heartbeat.
- Removed catalogue configurability tests and converted all executor tests to the canonical
  `EffectRequest` boundary.

#### Verification

| Command | Result |
|---|---|
| `uv run pytest coordinator/tests/test_device_registry.py::test_controller_session_changes_across_process_restarts coordinator/tests/test_runtime.py::test_steering_actuator_failure_is_nonfatal_and_disables_servotronic_output coordinator/tests/test_output.py::test_executor_rejects_raw_effects_outside_effect_request_boundary coordinator/tests/test_simulation_devices.py::test_neotrellis_rejects_button_and_led_traffic_without_fresh_operational_lease coordinator/tests/test_button_pad_firmware_source.py::test_local_fault_controller_lease_expiry_resumes_discovery -q` | Failed before fixes as intended: 4 failed, 1 passed; the firmware assertion was then tightened to the exact timeout branch. |
| `uv run pytest coordinator/tests/test_device_registry.py coordinator/tests/test_runtime.py coordinator/tests/test_runtime_activation.py coordinator/tests/test_output.py coordinator/tests/test_simulation_devices.py coordinator/tests/test_simulation_runtime.py coordinator/tests/test_button_pad_firmware_source.py coordinator/tests/test_config.py -q` | Passed; 148 tests. |
| `uv run python scripts/generate_custom_protocol.py --check` | Passed; generated custom protocol artifacts current. |
| `uv run python scripts/generate_live_contract.py --check` | Passed; generated live schema current. |
| `uv run pytest coordinator/tests` | Passed; 537 tests, with one existing Starlette/httpx deprecation warning. |
| `uv run ruff check coordinator scripts` | Passed after import-order cleanup. |
| `uv run mypy coordinator/src` | Passed; no issues in 62 source files. |
| `cd frontend && pnpm test` | Passed; 30 unit tests and 63 component tests across 18 component-test files. |
| `cd frontend && pnpm lint` | Passed. |
| `cd frontend && pnpm build` | Passed; TypeScript and Vite production build. |
| `pio run --project-dir devices/button-pad -t clean && pio run --project-dir devices/button-pad` | Passed; clean default Arduino Micro build, 34.6% flash and 40.8% RAM. |
| `pio run --project-dir devices/button-pad -t clean && PLATFORMIO_BUILD_FLAGS='-DDEVICE_ID=2' pio run --project-dir devices/button-pad 2>&1 \| tee /tmp/e87canbus-device-id-build.log && ! rg -n "redefined\|macro.*redefinition\|warning:.*DEVICE_ID" /tmp/e87canbus-device-id-build.log` | Passed; clean overridden-ID build, no `DEVICE_ID` macro-redefinition warning, 34.6% flash and 40.8% RAM. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- Controller sessions are process-local protocol leases, not persisted registry state. A
  cryptographically random nonzero seed changes the restart session without adding persistence;
  subsequent kernels in the process advance modulo 65535.
- An operational command remains accepted if its local Servotronic execution fails after the state
  commit. The synchronous failure is published as a nonfatal adapter fault, disables subsequent
  output, and does not claim physical application.
- The fixed v1 catalogue is not a runtime/configuration extension point. Catalogue entry
  dataclasses remain because they express the approved identity/version boundary, but callers
  cannot substitute alternate catalogues.
- Firmware-source tests cover state-machine source regressions that cannot be executed natively in
  the current PlatformIO project; compilation and shared host protocol vectors remain the available
  software evidence.

#### Deviations from the phase documents

- None. The audit removes implementation deviations from the approved design rather than changing
  the protocol or product specification.

#### Remaining limitations and physical evidence gates

- Physical NeoTrellis scanning, rendering, mapping, brightness/current limits, EEPROM endurance and
  persistence behavior, MCP2515 wiring, and transceiver behavior remain unverified.
- Physical Servotronic output and firmware remain out of scope.
- CAN ID collision capture, electrical compatibility, isolated 100 kbit/s bench evidence, explicit
  live K-CAN TX grant, and in-car validation remain mandatory before physical transmission.
- Random 16-bit controller sessions are not authentication and do not provide malicious-peer
  protection; those properties remain explicit v1 non-goals.

#### Final audit status

Completed. All known defects are repaired, the additional findings above are covered, required
repository checks and both clean firmware builds pass, and the implementation remains
software/simulation-only pending the documented physical evidence gates.
