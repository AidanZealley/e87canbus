# Phase 1 — Immediate Live-Safety Containment

## Goal

Correct the safety issues that should not wait for the event-kernel migration: default live
execution must be receive-only, normal `python-can` failures must not escape the adapter boundary,
and the current rate limiter must describe what it actually enforces.

## Why this comes first

The current default grants K-CAN TX and `runtime.start()` immediately sends two provisional `0x701`
frames. Those IDs are explicitly unvalidated for in-car use. Separately, `python-can` raises
`CanError` subclasses that are not caught by the runtime's `OSError` handling, so a normal adapter
fault can terminate the main loop or a reader thread.

Neither issue depends on the new kernel and both affect the current live runner.

## Design

### Safe composition defaults

- `default_config()` becomes the live-safe baseline: every network has `tx_enabled=False`.
- Add one explicit simulator composition function, such as `simulator_config()`, that enables K-CAN
  TX for the project button-pad/LED protocol. `SimulatorController()` uses it when no config is
  supplied.
- Tests and callers that need TX must opt in by constructing or replacing configuration. Do not add
  an environment variable or CLI flag that silently re-enables live TX; configuration loading is a
  separate future concern.
- The bench ping-pong executable remains explicitly writable because its entire command is a
  bench-only composition and it does not use `AppConfig`.

### SocketCAN exception normalization

- In `adapters/socketcan.py`, catch `can.CanError` from send and receive and raise `OSError` with the
  original exception as its cause.
- Keep `python-can` exception types out of `runtime.py` and application code.
- Add adapter tests for `CanOperationError` on both send and receive.
- Reader errors must be logged without killing the reader. Add a small bounded backoff for repeated
  receive failures so a broken interface cannot create a CPU/logging hot loop. Phase 5 replaces this
  temporary retry behavior with an explicit reader-fault input.

### Honest temporary rate-limit semantics

The current `min_id_gap_s` suppresses only an identical full frame on the same ID. Rename it to
`min_identical_frame_gap_s` and update code, tests, logs, and documentation. The aggregate
`max_frames_per_s` budget remains the hard flood bound until phase 4 replaces this wrapper.

Do not claim kernel-level listen-only mode. Documentation and logs should say "application TX
disabled" unless the SocketCAN interface is actually configured with hardware/kernel listen-only.

## Tests

- `default_config()` has no TX-enabled networks.
- `SimulatorController()` still starts with the expected button LEDs and routes replies on K-CAN.
- A live runtime built from defaults emits no startup frames.
- Explicit K-CAN TX configuration still works behind the limiter.
- `CanOperationError` is normalized for send and receive and isolated by existing runtime/reader
  behavior.
- Alternating payloads demonstrate that the temporary limiter is governed by the network budget,
  not a falsely named per-ID gap.

## Documentation

Reconcile `README.md`, `coordinator/README.md`, `docs/deployment.md`, `docs/simulation.md`, and
`protocol/custom_ids.md`. They must agree that:

- default live execution is application-level RX-only;
- K-CAN TX is enabled in simulator and isolated bench compositions only;
- `0x700`/`0x701` require collision validation before a future live grant; and
- kernel/hardware listen-only is a separate deployment defense.

## Out of scope

- Kernel-level SocketCAN listen-only setup.
- The final rate-policy design.
- Config-file or environment loading.
- Any steering output.

## Acceptance criteria

- Running the default live composition cannot call `SocketCanBus.send`, including during startup.
- A `can.CanOperationError` cannot escape `SocketCanBus.send` or `receive` as a python-can-specific
  exception.
- No docs describe the default live runner as K-CAN writable.
- All checks pass.

