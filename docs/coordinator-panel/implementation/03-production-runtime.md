# Workstream 3: production runtime integration

Status: not started.

## Task packet

### Outcome

Run the accepted shared services in the physical `car` and `bench` application compositions using
small UART and NetworkManager adapters. The coordinator must start and stop the accessories without
placing their state or failures in the kernel.

### Scope

- Add the `/dev/serial0` adapter for `STATUS <display>` output and `BUTTON` input.
- Add the backend for inspecting, activating, and deactivating only the preconfigured
  `e87canbus-hotspot` NetworkManager connection.
- Observe whether no client or at least one client is associated using the simplest target-suitable
  system command.
- Compose the shared services for `car` and `bench`; preserve the accepted simulator composition.
- Project existing `ControllerLoop` readiness/fatal health to coordinator status outside the kernel.
- Send starting, ready/fault, and graceful-off states at the appropriate application lifecycle
  points.
- Keep accessory waiting, command execution, and I/O outside the controller owner loop.
- Add only the runtime dependency and configuration values required by fixed hardware.
- Add focused adapter, lifecycle, and composition tests with process/serial fakes.

Use direct subprocess/serial-library calls behind the accepted seams. Do not introduce a general
command runner, reconnection supervisor, health subsystem, or background-task framework.

### Non-goals

- NetworkManager connection creation or credential handling at runtime.
- Automatic retries, backoff, persistence, device discovery, or a serial connection state machine.
- Kernel changes or accessory status in kernel snapshots/topics.
- Pi boot configuration, Polkit installation, firmware, or physical bench claims.
- Runtime hotspot editing or management of unrelated connections.

### Initial ownership

- New physical adapter modules under `coordinator/src/e87canbus/adapters/`.
- Minimal production accessory composition under `runners/`, `api/main.py`, or lifecycle files as
  required by the existing composition root.
- Dependency/configuration files strictly required by the runtime.
- Focused Python tests for those paths.
- This workstream record.

Application construction files previously touched by workstream 2 transfer to this owner for the
production extension. The accepted simulator behaviour must remain unchanged.

### Required seams

- Shared `PanelDisplay` to `STATUS <display>\n` once per second.
- Valid `BUTTON\n` to the shared panel-service operation.
- Shared hotspot backend operations to fixed NetworkManager commands/observations.
- Existing `ControllerLoop.snapshot()` to the four-value coordinator projection.

### Acceptance criteria

- `car` and `bench` select physical adapters; simulator selects no physical adapter.
- The application starts accessories without requiring a kernel change.
- Accessory I/O and command failure cannot block or fail coordinator readiness/CAN processing.
- Only the fixed hotspot connection can be changed by the adapter.
- Disable ends existing connection and activation; later activation cannot win after cancellation.
- UART lines are bounded; malformed input is ignored.
- There are no automatic hotspot command retries or bespoke serial reconnection machinery.
- Graceful shutdown sends `off` before closing the panel output when possible.

### Targeted verification

```bash
uv run pytest coordinator/tests/test_deployment_profiles.py \
  coordinator/tests/test_controller_loop.py
uv run ruff check coordinator/src/e87canbus coordinator/tests
uv run mypy coordinator/src/e87canbus
uv run lint-imports
```

Also run each new focused adapter or lifecycle test file. Use fakes for serial and system processes.
Do not claim physical NetworkManager, UART, cancellation, or client-observation validation in this
workstream.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Lifecycle/composition approach: `TBD`
- Fixed system commands and observations: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Hardware checks still required: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`
