# Phase 1: coordinator panel simulation and shared behavior

Status: complete.

## Outcome

Implement the coordinator panel and hotspot behavior end to end in simulator mode. At the end of
this phase the workbench must make the five-pixel indicator, hotspot button, laptop connection,
link loss, hotspot failure, coordinator failure, restart, and shutdown behavior tangible without
requiring a Raspberry Pi, RP2040, NetworkManager, UART, or NeoPixels.

This phase establishes the product behavior and the interfaces that physical adapters implement in
[Phase 2](phase-2-hardware.md). Phase 2 must not introduce a second state model or redefine the
indicator priority.

## Scope

- Add a pure local-controls model and panel-state derivation shared by simulated and physical
  compositions.
- Add an independent `LocalControlsService` beside `ControllerLoop`, with its own bounded owner,
  revision, snapshot, and failure boundary.
- Give local controls only a narrow coordinator condition: starting, ready, fault, or shutting down.
- Add in-memory panel and hotspot adapters.
- Publish a boot-scoped `local_controls` live-state topic.
- Add development-only commands that operate simulated causes.
- Add a compact coordinator enclosure representation to the simulator workbench.
- Reset local-controls simulation state with the existing simulation reset.

The local-controls subsystem is not a CAN device and must not be added to the custom CAN device
registry. Hotspot state must not enter vehicle `ApplicationState`, `CoordinatorKernel`,
`ControllerLoopSnapshot`, steering decisions, the CAN router, or CAN transmit policy. UART or
NetworkManager latency and failure must not delay or terminate vehicle control.

## State model

The shared model should use closed values rather than overlapping booleans.

Panel display state:

- `starting`
- `ready`
- `hotspot_waiting`
- `hotspot_connected`
- `fault`
- `off`

Hotspot lifecycle:

- `disabled`
- `activating`
- `active`
- `deactivating`
- `fault`

The published local-controls projection should contain at least:

- Desired panel display state.
- Effective simulated display state.
- Panel link status.
- Hotspot lifecycle.
- Whether a client is present.
- A bounded diagnostic message when the panel or hotspot adapter has failed.

Coordinator condition:

- `starting`
- `ready`
- `fault`
- `shutting_down`

This deliberately small value is the entire controller-to-local-controls contract. The adapter at
the application composition boundary derives it from controller lifecycle, readiness, and fatal
health. Local controls must not import controller snapshots, kernel health types, CAN networks, or
the reason for a controller fault.

The desired display state is derived in this order:

1. Coordinator condition `shutting_down` selects `off`.
2. Coordinator condition `fault` or a hotspot-control fault selects `fault`.
3. An active hotspot with a client selects `hotspot_connected`.
4. An active or activating hotspot without a client selects `hotspot_waiting`.
5. A ready coordinator selects `ready`.
6. Otherwise select `starting`.

Panel-link loss is not an input to the Pi's desired state. In simulation it causes the emulated
panel's effective display to become `fault`, representing the RP2040 heartbeat timeout. The Pi-side
projection simultaneously reports the disconnected link. Reconnection immediately applies the
latest complete desired state; missed intermediate states are not replayed.

## Hotspot behavior

A panel press is accepted only while the coordinator is ready and the hotspot is stable:

```text
disabled
  -> press -> activating -> active without client

active
  -> press -> deactivating -> disabled
```

Presses received while starting, shutting down, faulted, activating, or deactivating are ignored
and must not be queued for later execution. Client arrival and departure change only the client
observation and derived display; they do not activate or deactivate the hotspot.

The in-memory adapter should retain activating and deactivating long enough for those states to be
observable in the workbench. The duration must be deterministic under the simulator clock rather
than implemented as a browser delay.

Simulation reset represents a coordinator restart for this feature. It must force the simulated
hotspot off, clear simulated clients and injected adapter faults, create a visible startup state,
then converge to ready through the normal lifecycle. It does not claim to emulate Linux boot time.

## Placement and ownership

The smallest expected code layout is:

```text
coordinator/src/e87canbus/
├── local_controls/
│   ├── model.py
│   │   # Pure enums, immutable state, inputs, effects, snapshots, and derivation.
│   ├── ports.py
│   │   # Narrow panel, hotspot, coordinator-condition, and clock protocols.
│   └── service.py
│       # Independent bounded owner, lifecycle, revision, and notification callback.
├── runners/
│   ├── composition.py
│   │   # Builds both sibling services and the narrow controller-condition adapter.
│   └── simulation/
│       ├── local_controls.py
│       │   # In-memory panel, hotspot, client, link, and failure behavior.
│       ├── commands.py
│       │   # Closed simulation cause vocabulary.
│       └── api/
│           # Development-only request models and routes for those causes.
└── api/
    ├── internal/lifecycle.py
    │   # Orders startup/failure/shutdown across the two sibling services.
    ├── internal/live.py
    │   # Accepts independent notifications and composes reconnect snapshots.
    └── models/live.py
        # Versioned local-controls live payload.

coordinator/tests/
├── test_local_controls_model.py
├── test_local_controls_service.py
├── test_simulation_local_controls.py
└── test_local_controls_live.py

frontend/src/
├── components/coordinator-panel/
│   └── CoordinatorPanel.tsx
│       # Presentational five-pixel enclosure and its CSS animations.
└── components/simulator-workbench/
    └── SimulatorCoordinatorPanel.tsx
        # Live-state binding and simulator cause controls.
```

This is a proposed landing map, not a requirement to create empty packages or one-file facades.
If an existing contract or simulation route file remains clearer after the implementation is
small, it should be extended directly. Split a listed file only when it contains a real independent
responsibility.

The moving pieces and their relationships are:

```text
                       ┌──────────────────┐
CAN and HTTP ─────────▶│  ControllerLoop  │────────▶ CoordinatorKernel
                       └────────┬─────────┘
                                │ read-only lifecycle/readiness/fatal health
                                ▼
                      CoordinatorConditionAdapter
                       one closed four-state value
                                │
Browser causes ───────┐         ▼
                      ├▶ LocalControlsService ◀── timers and panel events
                      │   independent owner
                      │         │
                      │         ├──▶ InMemoryPanel
                      │         ├──▶ InMemoryHotspot
                      │         └──▶ derive_panel_state
                      │                    │
                      │                    ▼
                      │          LocalControlsSnapshot
                      │          independent revision
                      │                    │
                      └────────────────────┘

ControllerLoop notifications ─────┐
                                  ├──▶ LiveStatePublisher ──▶ browser
LocalControlsService notifications ┘       │
                                          └── composes both latest snapshots on reconnect
```

Responsibilities are deliberately narrow:

| Piece | Accepts | Owns or changes | Produces |
|---|---|---|---|
| Pure model | Immutable observations | No mutable state | Desired semantic display state |
| Coordinator-condition adapter | Read-only controller lifecycle, readiness, and fatal health | No state | One closed coordinator condition |
| Local-controls service | Coordinator condition, panel events, timers, and adapter observations | Hotspot transition ordering, independent revision, and latest projection | Adapter requests and local-controls snapshots |
| In-memory panel | Semantic state refresh and simulated link commands | Effective display and button events | Press/link observations |
| In-memory hotspot | Activate/deactivate and simulated client/failure commands | Hotspot lifecycle and client presence | Hotspot observations |
| Simulation API | Cause-oriented HTTP requests | No coordinator or LED state directly | Commands submitted to the local-controls owner |
| Live publisher | Independent notifications from both services | Latest pending value per topic | Combined reconnect snapshot and incremental events |
| Workbench component | Published semantic state | Browser animation phase only | Five-pixel presentation and cause controls |

The pure rule should remain approximately this small. Names may change to match the implementation,
but the dependency direction and priority are part of the specification:

```python
from dataclasses import dataclass
from enum import StrEnum


class CoordinatorCondition(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAULT = "fault"
    SHUTTING_DOWN = "shutting_down"


class HotspotLifecycle(StrEnum):
    DISABLED = "disabled"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAULT = "fault"


class PanelDisplayState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    HOTSPOT_WAITING = "hotspot_waiting"
    HOTSPOT_CONNECTED = "hotspot_connected"
    FAULT = "fault"
    OFF = "off"


@dataclass(frozen=True)
class PanelInputs:
    coordinator: CoordinatorCondition
    hotspot: HotspotLifecycle
    client_connected: bool


def derive_panel_state(inputs: PanelInputs) -> PanelDisplayState:
    if inputs.coordinator is CoordinatorCondition.SHUTTING_DOWN:
        return PanelDisplayState.OFF
    if (
        inputs.coordinator is CoordinatorCondition.FAULT
        or inputs.hotspot is HotspotLifecycle.FAULT
    ):
        return PanelDisplayState.FAULT
    if inputs.hotspot is HotspotLifecycle.ACTIVE and inputs.client_connected:
        return PanelDisplayState.HOTSPOT_CONNECTED
    if inputs.hotspot in {HotspotLifecycle.ACTIVATING, HotspotLifecycle.ACTIVE}:
        return PanelDisplayState.HOTSPOT_WAITING
    if inputs.coordinator is CoordinatorCondition.READY:
        return PanelDisplayState.READY
    return PanelDisplayState.STARTING
```

The panel-link condition is intentionally absent from `PanelInputs`. It changes the in-memory
panel's effective display and link diagnostics, not the Pi's desired display state.

The intended package boundaries are:

- `e87canbus.local_controls`: the complete hardware-independent sibling subsystem: pure values,
  derivation, ports, bounded owner, revision, and snapshot.
- `e87canbus.runners.simulation`: in-memory panel and hotspot implementations.
- `e87canbus.runners.composition`: selection of adapters and the one-way mapping from controller
  status into `CoordinatorCondition`.
- `e87canbus.api`: live-state serialization and composition lifecycle.

`LocalControlsService` is a sibling of `ControllerLoop`, not a child adapter or an extension of its
runtime. It must not call `CoordinatorKernel.dispatch`, construct domain events, import kernel
health types, add fields to `ControllerLoopSnapshot`, or share the controller inbox. A slow or
failed local-controls adapter must not delay the controller owner or change `/health/ready`.

Local-control changes advance their own boot-scoped revision and notify the existing bounded live
publisher directly. The publisher accepts independent notifications from both services, keeps only
the latest pending value for each topic, and includes the latest snapshots from both services when
a browser reconnects. It must not manufacture an application commit or increment a controller
revision for a local-controls update.

The two snapshots are not an atomic combined commit. That is intentional: no vehicle decision
depends on their combination, and complete repeated panel state plus reconnect snapshots guarantee
convergence. The live payload exposes the local-controls revision so clients can order its updates
independently.

Application lifecycle composition coordinates the siblings without a generic orchestration layer:

1. Start local controls in `starting` before controller initialization where possible.
2. Map controller readiness to `ready` after the existing controller startup succeeds.
3. Map an unexpected fatal controller stop or startup exception to `fault`.
4. Send `shutting_down` to local controls before stopping either service normally.

Simulation reset is the one cross-service development operation. Its route explicitly resets the
controller simulation and the local-controls simulation in a deterministic order, producing off,
starting, then ready. This does not require a transaction or a shared owner; failure is reported and
the next complete observation converges both services.

## Simulation commands

Development-only HTTP commands should support these causes:

- Tap the hotspot button.
- Connect or disconnect a simulated laptop.
- Disconnect or reconnect the simulated panel link.
- Enable or clear a simulated hotspot adapter failure.
- Trigger the existing authoritative fatal coordinator-health path.
- Reset the simulation.

Coordinator and CAN failure presentation should consume the existing controller health and reset
paths wherever possible. A second browser-only `coordinator_fault` flag must not compete with the
authoritative controller diagnostics.

The full local-controls command surface is installed only for the `simulator` profile. Physical
profiles must not expose endpoints that can toggle NetworkManager without a separate authorization
design.

## Workbench

Add a compact representation of the coordinator enclosure near the top of the simulator
workbench. It should show:

- Five pixels with the selected appearance and CSS animation.
- One hotspot button that invokes the same simulated panel input as the future physical button.
- Concise hotspot, client, panel-link, and fault status.
- Development controls for client presence, panel link, hotspot failure, and authoritative
  coordinator failure.

The browser renders semantic states. It must not assign arbitrary pixel colours through the API,
emulate RP2040 instructions, or emulate WS2812 timing. Animation timing may be tuned visually in
this phase; Phase 2 firmware should reproduce the accepted character rather than share rendering
code across languages.

### Accepted visual timings

- The white startup travel uses a 1.4-second cycle with a 140-millisecond stagger between adjacent
  pixels.
- The cyan hotspot-waiting pulse uses a 1.8-second cycle.

Both animations use a smooth ease-in-out character in the simulator. Phase 2 firmware should
reproduce these timings and character within the limits of its discrete animation loop; it does not
need to match browser animation frames exactly.

## Sequential agent workstreams

Phase 1 should be delivered as four sequential agent passes. They are deliberately not parallel:
each pass inherits the accepted implementation and contracts from the previous one. The original
request, this specification, and these acceptance boundaries remain the source of truth; the
primary agent owns interpretation and final implementation decisions.

### Phase 1A: sibling service foundation

Primary ownership:

- `e87canbus.local_controls`
- Focused model and service tests

Deliver:

- Closed state, input, effect, condition, link, hotspot, and snapshot values.
- Pure state derivation and transition behavior.
- Narrow panel, hotspot, coordinator-condition, and clock ports.
- An independent bounded `LocalControlsService` owner with its own lifecycle and revision.
- Fake-port tests for priority, button gating, transitions, failure isolation, deadlines,
  resynchronization, overload, and shutdown.

Review boundary:

- The subsystem runs entirely under tests without importing the kernel, `ControllerLoop`, FastAPI,
  serial, NetworkManager, or simulation packages.
- Slow or failing fake adapters cannot mutate controller state because no dependency path exists.
- No generic event bus, duplicate controller kernel, unused extension point, or runtime wiring is
  introduced.

### Phase 1B: simulator, application integration, and contracts

Primary ownership:

- `e87canbus.runners.composition` and `e87canbus.runners.simulation`
- Simulation-only API routes and models
- Application lifecycle and live publication integration
- Generated OpenAPI and live contracts

Deliver:

- The narrow read-only controller-condition adapter.
- In-memory panel and hotspot ports, including deterministic transitions and fault injection.
- Cause-oriented simulator commands and routes.
- Explicit cross-service simulation reset ordering.
- Lifecycle ordering for startup, startup failure, fatal controller failure, and shutdown.
- Independent local-controls notifications, revisioned live payload, incremental event, and combined
  reconnect snapshot.
- Backend end-to-end tests and regenerated contracts.

Review boundary:

- `CoordinatorKernel`, its input/effect vocabulary, and `ControllerLoopSnapshot` remain unchanged.
- Local-controls faults do not affect controller readiness or scheduling.
- `bench` and `car` expose no development hotspot command routes.
- Every backend semantic state is reachable without physical dependencies.

### Phase 1C: workbench UI

Primary ownership:

- Frontend live contract consumption and store state
- `CoordinatorPanel` presentation
- `SimulatorCoordinatorPanel` controls and integration

Deliver:

- Independent local-controls revision handling and reconnect hydration.
- Five-pixel semantic rendering and the accepted CSS animations.
- Hotspot button, simulated laptop, panel-link, and hotspot-failure controls.
- Accessible state labels and controls that remain understandable without relying on colour alone.
- Focused component and interaction tests.

Review boundary:

- The browser can request causes but cannot assign display state, arbitrary colours, hotspot state,
  or controller health directly.
- Animation phase remains presentation-only and never enters backend state.
- All six display states and disconnected-link diagnostics are inspectable in the workbench.

### Phase 1D: integration and acceptance review

Primary ownership:

- Cross-layer verification and defect resolution
- Accepted visual timing record
- Documentation synchronization

Deliver:

- Exercise every acceptance path through the real simulator HTTP, service, publication, store, and
  component boundaries.
- Verify restart, ordering, overload, faults, recovery, reconnect, and closed profile behavior.
- Run repository checks proportionate to the cross-layer change.
- Record the accepted animation timings and any deliberate differences the firmware must reproduce.
- Triage review findings as defects, optional improvements, or out of scope; resolve the defects in
  one bounded pass and return persistent disagreements to the primary agent.

Review boundary:

- Phase 1 acceptance criteria pass without physical dependencies.
- No Phase 2 UART, NetworkManager, privilege, firmware, or electrical work has leaked into scope.
- The implementation and all three coordinator-panel documents agree.

## Verification

Tests should provide meaningful confidence in:

- Exhaustive state-priority derivation.
- Exhaustive mapping from controller lifecycle, readiness, and fatal health into the narrow
  coordinator condition.
- Ignoring and not replaying presses outside stable ready states.
- Hotspot activation, client arrival/departure, and deactivation.
- Adapter failure and recovery.
- Panel-link timeout presentation and complete-state resynchronization.
- Simulation reset returning to a disabled hotspot and a new startup-to-ready lifecycle.
- Independent local-controls revision ordering, incremental publication, and combined reconnect
  snapshots without changing controller revisions.
- Local-controls overload or adapter failure leaving controller scheduling and readiness unchanged.
- Simulation routes being absent from `bench` and `car` where required.
- Workbench rendering and commands for every semantic display state.
- Generated OpenAPI, live-event, and frontend contracts remaining synchronized.

## Acceptance criteria

Phase 1 is complete when:

- Every indicator state in the context document can be reached from a realistic simulator cause.
- The hotspot cannot be activated by a press made before readiness or during a transition.
- Link loss visibly produces the emulated panel's local red failure state without changing the
  Pi's desired state.
- Reset and recovery converge from complete state rather than replayed events.
- `LocalControlsService` operates as an independently owned sibling and depends on the controller
  only through `CoordinatorCondition`.
- Local-control updates and failures do not mutate the vehicle kernel, controller snapshot,
  controller revision, readiness, or inbox.
- No coordinator-panel code depends on physical serial, NetworkManager, or NeoPixel libraries in
  simulator mode.
- The accepted visual behavior and animation timings are recorded for Phase 2.

## Non-goals

- UART framing or serial port setup.
- NetworkManager integration or Pi privilege configuration.
- RP2040 firmware and NeoPixel electrical behavior.
- Exact Linux boot-duration simulation.
- Hotspot authentication or exposing the coordinator API beyond its existing network policy.
- Ignition power-loss or hold-up power design.
