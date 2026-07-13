# Simulated Car UI

## Summary

Build a Vite and React development workbench that represents both the project's custom devices
and a simplified virtual E87. The purpose is to develop and exercise coordinator behavior without
needing regular access to the car, a breadboard, or completed device hardware.

The workbench should eventually let a developer:

- Operate virtual inputs such as the button pad, steering-wheel buttons, ignition, and light stalk.
- Change simulated vehicle readings such as speed, individual wheel speeds, RPM, temperatures,
  battery voltage, and DSC state.
- Observe outputs such as button LEDs, requested steering assistance, high-beam strobe state, and
  DSC requests.
- Inspect the CAN frames exchanged between simulated nodes and the coordinator.
- Introduce faults such as stale signals, missing nodes, malformed frames, and disconnected buses.
- Run repeatable scenarios and later replay real `candump` captures.

This is a realistic way to complete much of the software before hardware is available. It cannot
discover the real BMW protocol or prove physical actuator behavior, so vehicle captures and
controlled hardware validation will still be required.

## Architectural Principle

The simulator should exercise the same coordinator application logic that will run in the car. It
must not contain a separate copy of decisions such as button meanings or steering modes.

```text
Virtual button pad ─┐
Virtual E87 ────────┼─ simulated CAN ─ coordinator application ─ desired outputs
Fault controls ─────┘                                      │
                                                          ├─ virtual LEDs
                                                          ├─ virtual steering node
                                                          ├─ virtual lights
                                                          └─ virtual DSC state
```

When physical hardware is introduced, adapters change but application behavior remains the same:

```text
Same coordinator application
        ├─ simulated CAN and virtual devices during development
        └─ SocketCAN and physical devices in the car
```

The coordinator owns authoritative application state: modes, selected assistance, warnings,
configuration, and desired outputs. Each device owns physical truth and local safety, such as
button scanning, applied output, feedback, watchdogs, and failsafe behavior.

## Current State

The visual workbench currently provides a virtual NeoTrellis-style button pad, LED state, and CAN
trace. Button `0` is routed through the hardware-independent application controller and toggles
steering mode:

- Auto mode: button LED is blue.
- Manual mode: button LED is amber.

This already demonstrates the desired end-to-end path:

```text
React input → simulated device frame → coordinator state change
            → coordinator output frame → virtual device output → React display
```

The virtual button pad does not execute the compiled Arduino firmware. It models the device's CAN
contract in Python. Device firmware should remain small, with most application behavior in the
coordinator. Firmware logic that genuinely needs to be shared with simulation could later be
extracted into portable C++ and tested natively or compiled to WebAssembly, but full
microcontroller emulation is not an initial requirement.

## Proposed Workbench Areas

### Device Panel

- Virtual button pad with press, release, hold, and optionally chord behavior.
- LED output reflecting coordinator-owned state.
- Node connectivity, heartbeat age, firmware version, and reported faults.
- Future virtual steering-controller telemetry and other project nodes.

### Simulated Vehicle Panel

Inputs should begin as direct controls and later support scripted scenarios:

- Ignition and engine running.
- Vehicle speed and four individual wheel speeds.
- Engine RPM.
- Coolant, oil, intake, and ambient temperatures.
- Battery voltage.
- DSC state.
- MFL buttons and lighting/stalk inputs.
- Signal freshness and module availability.

### Vehicle Output Display

- Requested steering current or normalized assistance.
- Steering mode and manual assistance level.
- Steering-controller requested, applied, and measured state once modelled.
- Headlight and strobe state.
- DSC-off request and reported DSC state.
- Warning state and the reason each warning is active.

### CAN Tools

- Chronological frame trace with source node and decoded meaning.
- Raw arbitration ID and payload bytes.
- Filtering by bus, node, ID, or direction.
- Pause, clear, export, and replay.
- Clear distinction between assumed and capture-verified BMW definitions.

### Fault and Scenario Controls

- Stop or delay a periodic signal.
- Freeze speed at its last value.
- Send implausible wheel speeds.
- Disconnect a node or an entire bus.
- Inject malformed frames or incorrect counters/checksums.
- Simulate actuator feedback disagreement.
- Run named scenarios such as acceleration, overheating, lost speed data, and coordinator restart.

Scenarios should eventually be expressible as data so they can be run interactively and in
automated regression tests.

## Relationship to the In-Car Frontend

The React codebase can support two related experiences without making them the same screen:

```text
Shared frontend
├── Development workbench
│   ├── simulated vehicle controls
│   ├── virtual devices
│   ├── fault injection
│   └── CAN inspection
└── In-car UI
    ├── drive screen
    ├── detailed vehicle readings
    ├── module health
    ├── steering status and configuration
    └── settings and warning thresholds
```

Both should consume the same application-state API and reuse gauges, warning displays, module
status, and steering visualizations. Simulator-only controls should be enabled through an explicit
mode or backend capability, not mixed into the driving interface.

The proposed in-car UI on the Pi 4 and 5-inch touchscreen may include:

- Large temperatures, speed, RPM, and warnings on a glanceable drive screen.
- Tabs for detailed vehicle data, module status, steering, and settings.
- Steering mode, target assistance, measured current, command freshness, and faults.
- Backend-persisted warning thresholds.
- A steering-assistance curve editor with separate draft, active, and saved states.

The frontend is never part of a safety-critical control loop. Coordinator and device behavior must
continue safely if Chromium, the touchscreen, or the frontend process stops.

## Simulation Boundaries

Simulation can validate:

- Application architecture and state transitions.
- Network-scoped CAN encoding/decoding for the provisional K-CAN project protocol.
- Button mappings, modes, LED behavior, timing plans, and warning logic.
- Steering-curve calculations and target generation.
- Startup, reconnection, timeout, stale-data, and fault handling.
- API behavior, dashboard behavior, logging, scenarios, and regression tests.

Simulation cannot establish:

- Actual BMW arbitration IDs, payload layouts, scaling, or byte order.
- Rolling counters, checksums, message frequency, or gateway requirements.
- Whether replaying a frame produces the intended response.
- Servotronic valve current direction, electrical limits, or safe unpowered behavior.
- Real lighting, DSC, bus-loading, latency, and actuator behavior.

Provisional BMW definitions must be marked as assumed. They should only become verified after a
named capture, counter/timing analysis, and controlled validation on the specific car.

## Suggested Delivery Order

1. Preserve the existing button-to-coordinator-to-LED vertical slice.
2. Add simulated vehicle speed and expose it in the application snapshot.
3. Calculate and display steering target current using the existing fixed assistance curve.
4. Add Auto/Manual, assistance up/down, and pit-assist button behavior.
5. Add a basic dashboard showing speed, mode, target assistance, and signal freshness.
6. Add RPM and temperatures, including stale and over-temperature scenarios.
7. Add one backend-persisted warning threshold.
8. Add module heartbeats, reported state, and fault controls.
9. Add steering-curve visualization, followed by a validated draft/apply/revert editor.
10. Add scenario definitions and real CAN trace replay.
11. Replace individual simulated signals with capture-verified BMW decoders as data becomes
    available.

This order keeps each milestone visible and useful while progressively replacing assumptions with
real vehicle evidence.
