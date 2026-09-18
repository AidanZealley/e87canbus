# Slice 06: simulated independent Servotronic

- **Status:** Draft for approval
- **Depends on:** [Slice 02](02-simulated-button-pad.md) and
  [Architecture and boundaries](../architecture-and-boundaries.md)

## Outcome

The coordinator and simulator use the final Servotronic device configuration contract. The
simulated controller receives configuration over the device SSE endpoint, calculates automatic
assistance from locally received vehicle speed and reports its effective output through the device
status endpoint.

Slice 1.5 already removed the old physical and simulated Servotronic CAN protocol. Until this slice,
the coordinator retains desired steering state but has no Servotronic output transport.

## Configuration document

The role document contains one curve and one current mode:

```json
{
  "schema_version": 1,
  "curve": [
    {"speed_deci_kph": 0, "assistance_per_mille": 1000},
    {"speed_deci_kph": 100, "assistance_per_mille": 889},
    {"speed_deci_kph": 200, "assistance_per_mille": 778},
    {"speed_deci_kph": 300, "assistance_per_mille": 667},
    {"speed_deci_kph": 600, "assistance_per_mille": 381},
    {"speed_deci_kph": 1000, "assistance_per_mille": 0},
    {"speed_deci_kph": 1600, "assistance_per_mille": 0},
    {"speed_deci_kph": 2500, "assistance_per_mille": 0}
  ],
  "mode": {"type": "fixed", "output": 0.75}
}
```

The complete curve contains the existing eight-point schema grid and non-increasing per-mille
values. Automatic mode is `{"type":"automatic"}`. Fixed mode carries one finite output from `0.0`
through `1.0`.

The device knows only automatic and fixed mode. Manual UI levels remain coordinator state. For
`N` displayed levels, the coordinator resolves level `i` to `i / max(N - 1, 1)`. Maximum assistance
resolves to fixed output `1.0`.

The coordinator publishes a replacement document when the active curve, mode or resolved fixed
output changes. The simulated device treats it as persistent desired state, including fixed output.

## Simulated local control

The simulated device receives synthetic vehicle speed from simulated vehicle CAN, not from the
coordinator. In automatic mode it evaluates the configured curve using the approved monotone cubic
semantics and conformance cases. Missing, invalid or stale speed inhibits automatic output.

Fixed mode applies its configured output without requiring speed. Local device or actuator faults
may still inhibit all output. This preserves the approved rule that stored fixed configuration has
no lease or expiry.

## Status

The role-specific status is:

```json
{
  "speed_state": "fresh",
  "speed_deci_kph": 420,
  "configured_mode": "fixed",
  "requested_output": 0.75,
  "effective_output": 0.75,
  "inhibit_reason": null
}
```

`speed_state` is `unseen`, `fresh`, `stale`, `invalid` or `can_fault`.
`speed_deci_kph` is null when there is no valid observation. Outputs are finite values from `0.0`
through `1.0`. `inhibit_reason` is null or one of `no_speed`, `stale_speed`, `invalid_speed`,
`can_fault`, `output_fault` and `watchdog`.

Status changes are posted through the production endpoint. They do not become coordinator live
events or presence signals.

## UI and coordinator changes

The UI may choose its manual step count independently of the device. Existing button commands and
HTTP controls continue to manipulate coordinator steering state. The coordinator converts that
state into the complete Servotronic document rather than emitting repeated actuator commands.

The simulator runs only the independent device. Coordinator steering changes update its complete
desired document rather than emitting actuator commands.

## Outside this slice

This slice does not choose a real BMW speed signal, drive physical output or change vehicle wiring.

## Acceptance

The slice is complete when:

- a simulated Servotronic certificate receives only the Servotronic document shape;
- malformed curves, modes and fixed outputs are rejected atomically;
- automatic output follows the existing curve conformance cases from local simulated speed;
- missing, invalid and stale speed inhibit automatic output;
- fixed output remains independent of speed and accepts both `0.0` and `1.0`;
- changing UI step count changes coordinator resolution without changing the device schema;
- maximum assistance publishes fixed output `1.0`;
- power-cycle simulation restores the last valid document semantics;
- role-specific status passes through the production status handler; and
- no coordinator-facing CAN transport is reintroduced.
