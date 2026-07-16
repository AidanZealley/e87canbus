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
| 4 | Not started | — | — | — |
| 5 | Not started | — | — | — |

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
