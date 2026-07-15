# Phase 6: Simulation and custom-device convergence

## Goal

Complete the adapter-based simulation model so physical and emulated custom devices occupy the same
controller protocol paths, while the dashboard mirrors canonical state and can issue semantic
commands. Keep vehicle simulation narrow and honest.

This phase does not create a general digital-twin platform, simulate the whole BMW, invent device
acknowledgements or enable physical output.

## Preconditions

- Unified composition and frontend ownership are `Verified`.
- Current virtual bus, simulated button pad, simulated vehicle and steering actuator behavior has
  complete regression coverage.
- Custom protocol generation and the atomic LED snapshot contract pass their check modes.

## Device role configuration

For each repository-owned custom-device capability, composition selects one role:

```text
physical
emulated
observer
disabled
```

Meaning:

- `physical`: receive device inputs from the selected physical bus and send authorized effects to
  that bus.
- `emulated`: a virtual device emits and receives the same repository-owned wire protocol on a
  virtual bus.
- `observer`: mirror canonical controller/device state only and emit no device-originated traffic.
- `disabled`: capability is absent and effects follow the existing unavailable-capability policy.

Configuration rejects more than one ingress authority for the same capability. An observer is not
a second authority.

The ordinary dashboard device representation is an observer/control surface, not an emulator
merely because it is drawn like the physical device.

## Custom-device protocol parity

For the button pad:

- Physical and emulated implementations use the same generated arbitration IDs, payload lengths,
  button states and LED colour values.
- A simulated physical press encodes a real repository-owned button event and enters the normal bus
  reader/router/kernel path.
- The controller emits one complete `SetButtonLeds` snapshot through the normal effect executor.
- The emulated pad decodes that output using the same protocol contract and atomically replaces all
  LEDs.
- Invalid payloads preserve previous device state.

Do not create a simulator-only domain callback for button presses or LED state.

## Dashboard semantics

Separate two user intents in the development UI:

### Operate the controller

Controls such as maximum assistance issue semantic HTTP commands. The core applies the same domain
transition used after a physical input and effects synchronize the selected device.

```text
dashboard SetMaximumAssistance(true)
  -> controller
  -> steering/LED effects
  -> physical or emulated pad
  -> live projection back to dashboard
```

### Exercise an emulator

Explicit device-development controls operate an emulated device, which emits its wire message. They
are available only when that role is emulated and are labeled so they cannot be mistaken for an
ordinary controller command.

The same visual button may not silently switch between semantic-command and raw-emulator semantics.
Make the active source/mode visible in the development workbench.

## Desired and observed projections

Represent device projection honestly:

```text
source_mode
connected/last_seen only where evidence supports it
desired state
observed state or unknown
last output fault
```

- Controller-generated LED projection is desired state.
- An emulator may expose observed state because its decoder actually received the output frame.
- A physical pad without an acknowledgement remains `observed: unknown`.
- Do not infer physical categorical health from a simulator control or an output send.
- Existing simulator-only presentation health must remain explicitly labeled as simulation if
  retained.

No new heartbeat/status frame is introduced without a separately specified protocol change.

## Narrow vehicle signal source

Retain only signals consumed by current features:

- Speed.
- RPM.
- Oil temperature.
- Coolant temperature.
- Existing silence/stale/reset controls.

Development actions modify the simulated external signal source. It emits frames through the
selected virtual CAN topology; handlers never edit application samples directly.

Until verified BMW definitions exist:

- Synthetic extended IDs remain unmistakably simulation-only.
- `SimulationProtocolRouter` alone decodes them.
- The live router ignores them.
- The UI/docs do not imply byte-for-byte BMW protocol parity.

When a future verified production codec exists, the vehicle signal source may adopt that codec
without changing the controller core. That future work remains outside this phase.

Simple ramps, named scenarios or recorded replay may be added later, but are not required for this
phase and must not introduce a vehicle-physics model.

## Virtual transports

- The in-memory bus remains the normal deterministic development/test transport.
- `vcan` may be used for focused SocketCAN adapter integration checks.
- Both transports feed the same routed-frame/controller boundary.
- Tests use injected clocks rather than sleeping where deterministic time is required.

Avoid making `vcan` a mandatory developer-environment change.

## Reset and lifecycle

Simulation reset:

- Is serialized by the controller service.
- Reconstructs/reset adapters and trace identity without leaving old tasks/listeners.
- Returns vehicle signals to never-observed and device emulators to documented initial state.
- Produces a fresh complete published snapshot.
- Cannot reset or rewrite a physical device implicitly.

Switching a device source mode requires application restart unless a safe hot-swap contract is
explicitly implemented and tested. Runtime hot-swap is not required.

## Tests

- Physical/emulated duplicate ingress authority is rejected.
- Observer mode cannot emit CAN/device inputs.
- Emulated button events traverse encode, virtual bus, ingress, decode and core.
- LED effects traverse executor, wire encoding, virtual bus and emulator decode.
- Dashboard semantic commands update the selected physical/emulated output path without fabricating
  an input frame.
- Desired/observed/unknown states are projected honestly.
- Every simulated vehicle signal traverses its production-style ingestion boundary.
- Live router continues to ignore every synthetic vehicle identifier.
- Silence/stale/reset behavior remains independent and deterministic.
- Reset leaks no readers/tasks/socket subscriptions and cannot affect physical adapters.
- Optional `vcan` tests are clearly separated from ordinary in-memory tests.

## Browser/adapter checks

Exercise at least:

- Emulated pad press -> core change -> emulated LED result -> dashboard mirror.
- Dashboard maximum-assistance command -> core/effect -> emulated pad/dashboard convergence.
- Physical/observer composition when physical hardware is available read-only; otherwise record it
  as not run without blocking software verification.
- Vehicle signal set/silence/reset and resulting live-store states.
- Source-mode labels and unavailable emulator controls.

No real CAN TX or steering output is authorized for acceptance.

## Completion criteria

- Physical and emulated custom devices differ only at adapter composition after their shared wire
  contract.
- The dashboard mirror has no independent authoritative device state.
- Semantic controller control and emulator exercise are explicit, separate actions.
- One ingress authority is enforced per capability.
- Desired state is not falsely presented as physical observation.
- Vehicle simulation remains narrow, production-path and explicitly synthetic where evidence is
  missing.
- Reset and mode composition are deterministic and bounded.
- Protocol generation, focused tests, repository checks and required browser scenarios pass.
