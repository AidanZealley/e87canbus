# Workstream 4: Delete the project-device CAN platform

Status: not started.

## Task packet

### Outcome

The shared custom protocol, registry and ISO-TP platform are gone. With their final effect consumer
removed, the generic effect execution stack is gone too.

### Scope

- Delete `protocol/custom.toml`, generated custom protocol output and documentation, its generator
  script and CI drift check.
- Delete registry discovery, heartbeat, acknowledgement, device sessions, lifecycle state,
  catalogue metadata and registry diagnostics.
- Retain or relocate one lean closed `DeviceRole` only for later certificate identity. Use canonical
  hyphenated role values and no catalogue facade.
- Delete Python and embedded ISO-TP transports and consumerless dependencies.
- Reduce CAN protocol code to vehicle frame types and decoders still used by the coordinator.
- Remove custom IDs, device-source configuration and project-device deployment choices.
- Remove project-device simulation commands, API routes, topology and lifecycle projections.
- Delete `ApplicationEffect`, `EffectRequest`, `EffectExecutor`, effect failure inputs and
  `Commit.effects` now that no accepted effect remains.
- Keep low-level CAN endpoint send operations used by vehicle simulation, but remove configured live
  transmit authority and unused rate-policy machinery.
- Update current documentation and ADR status notes without rewriting historical decision bodies.

### Non-goals

- Removing vehicle CAN decoding, SocketCAN receive, vehicle simulation or unrelated coordinator
  panel hardware.
- Independent device authentication, persistence, HTTP or SSE.
- An empty output service, vehicle action union, encoder registry or future transmission hook.

### Initial ownership

- custom protocol sources, generator, CI and documentation
- generated protocol, registry, device catalogue and ISO-TP packages
- configuration, deployment and composition device-source and TX fields
- output adapter and effect/failure portions of kernel, runners and diagnostics
- project-device simulation API, commands and topology
- embedded ISO-TP library, package dependencies, tests and exports

Integration exception: make the minimum commit and runtime signature changes required to remove
effects. Workstream 5 owns the broader surviving-contract audit.

### Required seams

- Vehicle `CanFrame`, routed network identity and decoding remain independent of deleted generated
  protocol code.
- Simulation can still inject vehicle frames through the production decoder.
- SocketCAN and in-memory endpoints may implement `send`, but live application composition creates
  no transmitter and exposes no command that can call it.
- Kernel commits describe accepted state and changed projections only.
- No compatibility module or no-op executor preserves an old import path.

### Acceptance criteria

- Repository searches find no custom protocol source/output/generator, registry, heartbeat,
  acknowledgement, ISO-TP, `DeviceSource`, project-device simulator control or old firmware.
- The generic effect and effect-failure architecture is absent.
- Runtime and simulator composition start without a device catalogue, registry or peer graph.
- Vehicle decoding and simulation still cross the real frame decoder.
- Live composition has no configured CAN transmit grant or rate policy.
- Dead dependencies, tests, fixtures, exports and documentation are removed.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_architecture.py hosts/tests/test_config.py hosts/tests/test_deployment_profiles.py hosts/tests/test_controller_loop.py hosts/tests/test_runtime.py hosts/tests/test_simulation_bus.py hosts/tests/test_simulation_runtime.py hosts/tests/test_simulator_api.py hosts/tests/test_live.py
uv run mypy
uv run ruff check hosts
uv run lint-imports
git diff --check
```

Run repository searches for every deleted filename and symbol, the affected frontend tests and type
checks, and the repository dependency lock/check command if dependencies changed.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 4 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/04-delete-device-can-platform.md, all accepted dependency handoffs, Slice 1.5, ADR 0018 and the ADRs it supersedes. Inspect the complete repository for custom protocol, generated protocol, registry, heartbeat, acknowledgement, ISO-TP, device source/lifecycle, firmware, project-device simulation, effect execution, output failures and CAN TX configuration. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check complete deletion, canonical lean DeviceRole, effect-free commits, no live transmit authority, and preservation of vehicle frames, decoding, simulation and low-level endpoint capabilities. Reject no-op shells, aliases, compatibility facades and future-action abstractions." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 4 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking incomplete deletion, dependency, commit-contract or vehicle-CAN regression. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
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
