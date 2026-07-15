# Phase 4: Device role projection

## Current contract

Unified-controller Phase 6 owns the current custom-device contract. Each repository-owned device
capability selects exactly one source at process startup:

```text
physical | emulated | observer | disabled
```

For the current button pad, `devices.state` publishes:

- the selected source mode;
- connection and last-seen values only when an adapter has evidence;
- the controller-desired 16-colour LED snapshot;
- the device-observed 16-colour LED snapshot, or unknown;
- the last output fault, if effect execution failed.

The physical button-pad protocol has no acknowledgement. A successful send therefore cannot prove
connection or LED observation. The emulator may report connection and observed LEDs because its
virtual endpoint exists and its decoder actually receives a complete valid generated `0x701`
snapshot. Observer mode mirrors controller desire without originating device traffic, while a
disabled capability is absent.

The simulated steering actuator remains the separate `steering_controller` actuator projection; it
is not a custom-device health entry.

## Development controls

The `/dev` workbench separates two intents:

- **Operate controller** sends semantic HTTP commands such as maximum assistance. It never
  fabricates a button input frame.
- **Exercise emulator** exposes explicit per-button press/release controls only when the selected
  source is `emulated`. These controls encode the generated `0x700` wire message and use the normal
  virtual-bus/router/kernel path.

There is no mutable presentation-health API. Explicit press/release is the only emulator input
control; device projection is derived from selected adapters, controller desire, decoded
observation and runtime fault evidence.

## Presentation rules

- Show the source mode explicitly.
- Show connected or disconnected only when `connected` is non-null; otherwise say connection
  unknown.
- Never display desired LEDs as device observation. If observed LEDs are unknown, label the desired
  fallback explicitly.
- Disable emulator controls for physical, observer, disabled and unsynchronized states.
- Keep semantic controller controls available whenever the live controller is synchronized,
  independently of whether a device emulator is selected.
- Missing device entries are unavailable capabilities, not inferred failures.

## Verification

- Composition rejects missing/duplicate role selections and emulated K-CAN without authorized
  virtual output.
- Explicit emulator press/release traverses generated encode, virtual bus, ingress router and core.
- LED effects traverse executor, generated encoding, virtual bus and emulator decoding.
- Observer and disabled roles cannot originate button input or receive button-pad output.
- Physical connection and observation remain unknown without protocol evidence.
- Reset releases the previous virtual topology and restores documented initial projections.

See [unified-controller Phase 6](../unified-controller/06-simulation-and-device-convergence.md) for
the complete architecture and acceptance criteria.
