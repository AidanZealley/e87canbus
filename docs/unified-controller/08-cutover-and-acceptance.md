# Phase 8: Integrated cutover and acceptance

## Goal

Verify the complete unified architecture, remove obsolete transport/composition paths and leave one
clear end-to-end system. Demonstrate simulation parity, reconnect behavior, bounded resource use and
frontend responsiveness without enabling unverified physical output.

## Preconditions

- Phases 1-7 are at least `Implemented`.
- No phase has an unresolved state ownership, safety, migration or public-contract blocker.
- Every temporary compatibility path is inventoried with a current consumer check.
- Integrated tests use an isolated development database and no production transmit capability.

## Legacy removal

After proving there are no remaining consumers, remove:

- The raw WebSocket live-snapshot endpoint and connection manager.
- Live snapshot storage/merge behavior in TanStack Query.
- Separate simulator-only application composition/state owner.
- Compatibility facades that can construct a second runtime.
- Old broad invalidation messages and refresh-all handlers.
- Superseded direct-fetch component paths and simulator response snapshots.
- Unused types, tests and documentation describing the retired ownership model.

A CLI alias may remain only if it is a documented thin wrapper around the canonical composition.

Run dead-code/import searches after removal. Do not retain an old path “just in case” without a
named external consumer and explicit follow-up owner.

## Automated repository checks

Run from repository root unless a command requires `frontend/`:

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
bash -n scripts/*.sh

pnpm test
pnpm lint
pnpm typecheck
pnpm build

git diff --check
```

Run any socket-contract generation/check command introduced in Phase 4. Record exact counts,
warnings and failures. New warnings caused by the roadmap must be resolved or explicitly block
verification.

## Architecture acceptance

Prove through tests and inspection:

- One canonical application composition starts in live-listen-only and simulated presets.
- One controller owner processes CAN, timers, commands, faults and shutdown.
- No API/emulator/socket path mutates operational state directly.
- Physical/emulated custom devices share the generated protocol path.
- One ingress authority per capability is configuration-enforced.
- All real output capabilities remain absent by default.
- HTTP commands/resources and Socket.IO live state have no overlapping authority.
- Socket publication is commit-driven, topic-bounded and reconnect-snapshot based.
- Zustand contains only current live state; TanStack Query contains only HTTP server state.
- SQLite contains only durable desired configuration.
- Every queue, trace and publication buffer is bounded.
- Live router still rejects all unverified synthetic vehicle identifiers.

## End-to-end scenarios

### Simulated custom device

1. Start the normal simulated preset.
2. Press a button through the explicit emulated-device control.
3. Verify a generated CAN event enters the virtual bus and production controller path.
4. Verify the resulting complete LED effect returns through the virtual bus and device decoder.
5. Verify the dashboard mirror converges through Socket.IO/Zustand rather than local mutation.

### Semantic dashboard control

1. Set maximum assistance from the dashboard.
2. Verify one HTTP command acknowledgement.
3. Verify controller state/effects change once.
4. Verify emulated pad and dashboard mirror converge.
5. Repeat the same set command and verify it does not reverse state.

### Vehicle signals

1. Set speed, RPM and both temperatures from development controls.
2. Verify each emits its simulation-only CAN frame and reaches normal ingestion.
3. Silence one signal and demonstrate independent staleness.
4. Reset and demonstrate never-observed state with a fresh synchronized snapshot.

### Durable resources

1. Update settings/profile resources and verify exact Query cache replacement.
2. Use a second client to verify precise `resources.changed` invalidation.
3. Create a stale expected revision and confirm the committed winner is preserved.
4. Restart the controller and verify durable data plus runtime configuration reconciliation.

### Reconnect and restart

1. Interrupt the browser connection while controller/CAN simulation continues.
2. Reconnect and verify a complete current snapshot, not an event replay.
3. Restart the controller and verify `boot_id` resets all prior live revisions.
4. Confirm durable Query resources remain/reconcile and transient telemetry is never presented as
   current across the restart.

### Failure and overload

1. Exercise controller inbox overflow in an isolated test and verify bounded fail-safe behavior.
2. Stall a socket/trace consumer and verify controller latency/effects remain independent.
3. Inject output and SQLite failures and verify their distinct health/resource behavior.
4. Confirm recovery/restart behavior matches Phase 7 policy.

## Browser matrix

Use the collaborative browser against isolated backend/frontend processes. Check `/dev` and every
current `/car` route in light and dark where presentation can differ.

Inspect:

- Initial load, reconnecting, synchronized and incompatible-protocol states.
- Normal, never-observed and stale telemetry.
- Steering/button/device updates without adjacent panel fading.
- Each operational/development mutation pending, success and failure state.
- Settings/profile precise mutation and conflict behavior.
- Trace closed, open under traffic, closed again and reopened.
- Repeated navigation between routes without extra socket connections/listeners.
- Existing 800x480 car-display requirements from `docs/car-frontend`.

Check no horizontal overflow, clipped controls or color-only status regressions. Physical display
touch tuning remains an explicit manual check if target hardware is unavailable.

## Performance and memory acceptance

Run sustained expected and elevated simulated traffic in both React development and production
builds. Include route navigation, background/foreground cycles, repeated commands and trace
subscription cycles.

Record at warm-up and later checkpoints:

- Browser socket and listener count.
- Zustand live/trace retained sizes.
- TanStack Query entry/observer counts.
- DOM node count.
- Relevant browser Performance entry count.
- Heap snapshots or comparable retained-object evidence after garbage collection.
- Backend process memory.
- Controller inbox depth/latency and publisher pending-topic count.

Acceptance requires bounded counts and a post-warm-up plateau/sawtooth consistent with garbage
collection, with no monotonic retained growth attributable to socket events, query cache updates,
traces or React subscription duplication. Record duration and traffic rate rather than claiming
“no leak” from a brief observation.

The original development crash must not reproduce. Do not disable development instrumentation,
reduce features or change the user's development environment as the remedy.

## Optional physical/read-only checks

When hardware is available, read-only checks may verify:

- The unified live preset opens configured K-CAN/PT-CAN/F-CAN interfaces.
- Recognized repository-owned input reaches the same controller/socket/frontend path.
- Dashboard observer state follows canonical state.

Do not enable CAN TX or physical steering merely for roadmap acceptance. Record physical checks as
not run when unavailable rather than replacing them with simulation claims.

## Documentation and handoff

- Update coordinator/frontend READMEs to describe the final one-process operation and data
  ownership.
- Update setup/simulation docs and CLI examples.
- Remove or correct documentation for legacy WebSocket/simulator composition.
- Ensure public HTTP/Socket.IO schemas and generated TypeScript types agree.
- Append exact automated, browser, soak and optional physical evidence to the implementation log.
- Record any remaining hardware-evidence work under existing `docs/requires-hardware` boundaries.

## Completion criteria

- Every earlier phase completion criterion is satisfied.
- Only one controller/application architecture remains executable.
- Legacy WebSocket, snapshot-query and independent simulator ownership are removed.
- All automated and contract checks pass.
- End-to-end simulation, command, resource, reconnect and failure scenarios pass.
- Browser regression passes without adjacent loading fades or duplicate connections/listeners.
- Sustained development and production evidence demonstrates bounded retained state and the original
  crash does not reproduce.
- Default live operation remains listen-only and no unverified hardware claim is made.
- Documentation describes actual final behavior and remaining physical evidence honestly.
