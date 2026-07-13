# Phase 2 — Policy Proof and Legacy Cleanup

## Goal

Prove that full snapshots and the holistic network output policy compose safely, then remove every
remaining indexed-LED assumption from code, tests, and documentation.

## Policy proof

- Prove one full LED snapshot consumes exactly one network-window entry regardless of how many
  positions differ.
- Prove alternating snapshots on `0x701` and frames spread across different IDs share the same
  network budget.
- Prove a dropped snapshot is not queued or delivered later when the window refills.
- Prove the next accepted full snapshot replaces the complete simulated device state and therefore
  repairs any missed intermediate LED state.
- Prove startup/reconnection synchronization uses one full snapshot and still passes through the
  same executor and network policy.

Document the default network ceiling as a coordinator-wide flood bound. Explain its relationship to
the configured CAN bitrate and intended application allocation; do not justify it using LED count,
current startup frame count, or human button timing. If the existing value cannot be justified,
change it explicitly with deterministic tests rather than adding a second limiter.

## Cleanup audit

Delete or rename all remaining forms of:

- `LedUpdatePayload`, `SetButtonLed`, `led_update`, and index/colour byte constants;
- frontend merge-one-LED helpers;
- tests expecting sparse LED dictionaries;
- documentation showing `0x701 [button_index, colour]`; and
- temporary adapters or compatibility names introduced during phase 1.

Search historical hardening documents only to distinguish intentional history from current guidance;
do not rewrite completed implementation logs to hide the migration history.

## Documentation

Reconcile the root, coordinator, protocol, bench, simulation, deployment, device, and wiring guides.
They must agree that:

- `0x701` is DLC 8 and carries a packed complete snapshot;
- the IDs remain provisional and collision-gated;
- one accepted frame replaces all 16 logical colours;
- the network safety budget is holistic; and
- physical rendering remains gated on phase 3 evidence.

## Acceptance criteria

- No current production code or current-facing documentation describes indexed LED updates.
- Drop and later-convergence behavior is deterministic and tested without sleeps.
- There is one publication shape and one frontend state-replacement path.
- The TX policy contains no LED-count-derived or per-ID burst field.
- All backend, frontend, generator, and firmware checks pass.
