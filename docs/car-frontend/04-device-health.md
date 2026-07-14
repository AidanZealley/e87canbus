# Phase 4: Device health projection and simulation

## Goal

Introduce a small, explicit device-health contract for the button pad and steering controller, add
deterministic simulator controls for its presentation states and expose it in authoritative
snapshots. Do not infer or claim real heartbeat criteria in this phase.

## Contract

Add a closed status enum:

```text
online | degraded | offline
```

Add a snapshot value:

```json
{
  "id": "button_pad",
  "label": "Button pad",
  "status": "online",
  "reason": null
}
```

Initial device IDs are exactly:

- `button_pad`
- `steering_controller`

`id` is stable and machine-readable; `label` is display text. `reason` is a stable
machine-readable string or `null`. Simulation uses:

- `simulated_degraded`
- `simulated_offline`

Online simulation state has a null reason.

The top-level simulator snapshot contains a complete `devices` array in stable order: button pad,
then steering controller. Do not make clients infer device state from network-node strings or the
steering watchdog.

## Meaning and evidence boundary

The intended future meanings are:

- **Online:** Expected communication and all required capabilities are healthy.
- **Degraded:** Communication exists, but a required capability, timing guarantee, feedback path or
  output behavior is impaired.
- **Offline:** No usable communication exists within a device-specific timeout.

Possible future reasons include `watchdog_timeout`, `stale_heartbeat`, `output_failure` and
`malformed_frames`, but this phase must not implement those transitions without device-specific
evidence. Manually selected simulation state is a UI test input only.

## Simulator ownership

Store the simulated device states inside the single-owner `SimulationEngine` session. Add a closed
command value that contains a validated device ID and status. The engine command match updates one
device, produces the usual revisioned snapshot event and leaves the other unchanged.

Rules:

- New simulation session starts with both devices online.
- Reset restores both online.
- Repeating the same status is safe and produces an authoritative response.
- `degraded` maps to `simulated_degraded`.
- `offline` maps to `simulated_offline`.
- `online` clears the reason.
- The presentation state must not disable existing simulated behavior; it is not yet a behavioral
  hardware fault injector.

## API

Add:

```text
PUT /api/simulation/devices/{device_id}/status
```

Body:

```json
{"status": "degraded"}
```

Behavior:

- Strictly validate device and status.
- Return 404 or the project's established typed missing-resource response for unknown device IDs.
- Return 422 for an unsupported status/body.
- Submit through the bounded simulator command queue.
- Return the normal slim snapshot on success.

Do not create separate endpoints for each device or state.

## Frontend development controls

Extend simulator snapshot/socket types with `devices`. The empty snapshot may contain both known
devices as offline/unavailable placeholders or an empty array, but the display layer must not treat
missing entries as online.

Add a typed API function and compact status selectors for both devices to the existing simulated
vehicle controls card. Use the installed Select primitive. Disable duplicate commands while a
mutation is pending and update from the authoritative returned snapshot.

The controls must make all six device/status combinations easy to exercise without changing CAN
traffic or steering behavior.

## Car presentation contract

Phase 6 will render a minimal overview footer:

- Online uses a positive/green token or named Tailwind color.
- Degraded uses amber.
- Offline uses destructive/red.
- Visible text includes the device label and status; color is not the sole signal.
- The reason is available through accessible text or tooltip without increasing footer density.
- A missing device entry is rendered as unavailable/offline, never online.

## Tests

- Initial snapshot contains both online devices in stable order.
- Each device supports online, degraded and offline independently.
- Reasons map and clear correctly.
- Reset restores online.
- Invalid device and invalid status fail without changing either device.
- Command queue behavior and snapshot publication match other simulator commands.
- Initial and reconnect WebSocket snapshots contain the complete device array.
- Frontend selector sends the exact device ID and status.
- Missing snapshot entries cannot render as online.
- Existing steering watchdog tests remain independent of simulated presentation state.

## Completion criteria

- Consumers receive explicit typed device state without reverse-engineering other snapshot fields.
- `/dev` can create every required footer presentation state.
- Simulation reset is deterministic.
- No real heartbeat, timeout or fault-detection behavior is claimed or invented.
- Device state remains an extensible snapshot boundary rather than UI-only constants.

