# Workstream 3: production runtime integration

Status: accepted.

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

- Base commit: `0d698ac93ef8c435ab93e76febefc0a7f8f711e3`
- Outcome: Added the fixed physical UART and NetworkManager edges and composed them for the `car`
  and `bench` application profiles without changing the coordinator kernel or the accepted
  simulator path.
- Files changed: `coordinator/src/e87canbus/adapters/coordinator_panel.py`,
  `coordinator/src/e87canbus/adapters/networkmanager_hotspot.py`,
  `coordinator/src/e87canbus/runners/coordinator_panel.py`,
  `coordinator/src/e87canbus/api/internal/lifecycle.py`,
  `coordinator/src/e87canbus/api/main.py`, `coordinator/tests/test_coordinator_panel_adapter.py`,
  `coordinator/tests/test_networkmanager_hotspot.py`,
  `coordinator/tests/test_physical_coordinator_panel.py`, `pyproject.toml`, `uv.lock`, and this
  record.
- Lifecycle/composition approach: Physical profiles own two direct daemon threads with one narrow
  handoff: the UART owner polls bounded input and sends the latest semantic display once per second,
  while the state worker performs synchronous NetworkManager observation and shared-service button
  handling. A locked latest-display value and direct button queue are sufficient; no scheduler or
  generic task framework is involved. This split is necessary because the bounded NetworkManager
  and station commands may legitimately take longer than the firmware's three-second link timeout,
  so a single sequential loop cannot guarantee the fixed UART cadence. When the UART owner receives
  a physical button line, it captures the current coordinator projection with that event. The state
  worker later passes the captured value directly to `PanelService`, which still owns readiness
  gating before any potentially slow hotspot work. Thread startup returns immediately and all
  accessory work remains outside the controller-owner thread. The FastAPI lifespan starts the
  accessory while the controller is starting and stops it before the controller adapter; graceful
  stop writes `off` directly before closing UART. Unexpected accessory failure closes UART without
  sending `off`, allowing the firmware heartbeat fault to remain visible.
- Fixed system commands and observations: Activation uses `nmcli --wait 0 connection up id
  e87canbus-hotspot`, allowing a later fixed `nmcli connection down id e87canbus-hotspot` to cancel
  activation. Observation uses `nmcli --get-values GENERAL.STATE connection show id
  e87canbus-hotspot`; an activated connection uses `iw dev wlan0 station dump` only to distinguish
  no station from at least one station. Each direct subprocess call has a five-second bound and no
  retry.
- Decisions: UART protocol constants remain fixed beside the adapter: `/dev/serial0`, 115,200 baud
  and a 64-byte line bound. The only added runtime package is `pyserial`. UART input and heartbeat
  remain together under one port owner; only potentially slow hotspot state derivation is separated.
  A simplification pass removed any need for configurable hardware names, a general scheduler,
  reconnection machinery, duplicate hotspot/panel rules, or an additional UART thread.
- Verification: Initial implementation verification used `uv run pytest
  coordinator/tests/test_coordinator_panel_adapter.py
  coordinator/tests/test_networkmanager_hotspot.py
  coordinator/tests/test_physical_coordinator_panel.py
  coordinator/tests/test_deployment_profiles.py coordinator/tests/test_controller_loop.py` (33
  passed); `uv run pytest coordinator/tests/test_simulator_api.py` (42 passed); `uv run ruff check
  coordinator/src/e87canbus coordinator/tests` (passed); `uv run mypy
  coordinator/src/e87canbus` (passed); `uv run lint-imports` (2 contracts kept).
- Hardware checks still required: Physical `/dev/serial0` transport and heartbeat, NetworkManager
  permission and state output on the target Pi, `wlan0` station observation, activation
  cancellation, client disconnect on disable, and end-to-end panel button behaviour.
- Specification drift: `None`.

## Independent review

- Reviewer: `Codex /root/ws3_review`
- Verdict: `Changes required`
- Required findings:
  - `PhysicalCoordinatorPanel._run()` performs the one-second UART heartbeat only after the
    synchronous hotspot observation completes. An activated observation can execute two subprocesses
    with independent five-second timeouts, so ordinary bounded NetworkManager or `iw` delay can
    suppress status for longer than the firmware's three-second established-link timeout. A focused
    fake with `observe()` taking 3.2 seconds produced writes at 0.00, 3.20, and 6.41 seconds, causing
    a false red panel-link fault despite the coordinator thread remaining healthy. This violates the
    fixed once-per-second heartbeat and immediate accessory-status requirements. Keep status output
    cadence independent of blocking hotspot commands/observations with the smallest direct
    production composition, and add a focused timing test proving a slow fake backend cannot delay
    the UART heartbeat beyond its required cadence.
  - The runner processes queued `BUTTON` lines before refreshing the coordinator projection, while
    `PanelService` retains only the projection from the previous heartbeat. A focused reproduction
    changed the controller from `CREATED` to ready immediately after the initial refresh, then sent
    `BUTTON` before the next heartbeat; activation count remained zero. The inverse window can also
    accept a press after readiness or health has been lost. This violates the rule that presses are
    gated by the coordinator's current readiness. Refresh the shared panel service's coordinator
    status before applying a queued press (without duplicating the gating rule outside that service),
    and protect the ready-transition/button path with a focused test.
- Optional observations: `None`.
- Questions for orchestrator: `None`.

## Resolution

- Finding dispositions: Accepted both required findings. The UART heartbeat must remain within its
  one-second cadence while NetworkManager observation is bounded but slow, and button handling
  must use a current coordinator-readiness projection rather than the previous heartbeat's cached
  value. Closure escalation accepted: "current" means status captured when UART receives the
  physical press. The shared button operation must apply that captured status before any hotspot
  observation so the event cannot be retained across readiness transitions.
- Simplification/deletion pass: Replaced the single mixed I/O loop with exactly two concrete
  responsibilities rather than layering timeout flags onto it: one UART owner for parsing and
  heartbeat timing, and one state worker for the already synchronous shared services and fixed
  NetworkManager backend. They exchange only the latest `PanelDisplay` and button events carrying
  their event-time `CoordinatorStatus`. UART reading was kept with heartbeat output so the serial
  port still has one owner. The escalated correction removed the blocking readiness refresh from the
  state worker: the UART owner now captures coordinator status for each complete `BUTTON`, and the
  state worker passes it directly to the shared event-time gate. Focused blocking-observation tests
  confirm a pre-ready press is discarded even if readiness arrives before processing, while a press
  received ready remains valid if readiness is lost during already queued hotspot work. The
  slow-backend timing test continues to protect the real three-second firmware risk. No duplicated
  gate, scheduler, task framework, retry, reconnection state, configuration, façade, or obsolete
  readiness test remains.
- Final verification: `uv run pytest coordinator/tests/test_panel.py
  coordinator/tests/test_hotspot.py coordinator/tests/test_coordinator_panel_adapter.py
  coordinator/tests/test_networkmanager_hotspot.py
  coordinator/tests/test_physical_coordinator_panel.py
  coordinator/tests/test_deployment_profiles.py coordinator/tests/test_controller_loop.py` (43
  passed); `uv run pytest coordinator/tests/test_simulator_api.py` (42 passed); `uv run ruff check
  coordinator/src/e87canbus coordinator/tests` (passed); `uv run mypy
  coordinator/src/e87canbus` (passed); `uv run lint-imports` (2 contracts kept); `git diff --check`
  and `uv lock --check` (passed). The first final simulator-suite attempt observed the existing
  timing-sensitive reset RGB assertion documented by the accepted simulator workstream; an
  unchanged complete rerun passed.

## Closure review

- Verdict: `Accepted`
- Remaining required findings: `None`. The UART owner now captures a `CoordinatorStatus` with each
  complete `BUTTON` line, the typed queue preserves it, and `PanelService.button_pressed()` installs
  and gates that status before any hotspot observation. Focused blocking-backend tests confirm a
  pre-ready press remains ignored after readiness arrives and a ready press remains valid when
  processed across a later readiness change. The simulator calls the same required shared-service
  seam. The 3.2-second slow-observation test still confirms the independent UART owner maintains the
  one-second heartbeat, with no release-blocking race or failure-isolation regression found. The
  focused panel, physical composition, and simulator suites pass (51 tests), as do focused Ruff and
  coordinator mypy checks.
- Accepted commit: `f211f94c1eb7052866ed5e40250a6e5d558f1077`
