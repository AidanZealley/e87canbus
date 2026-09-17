# Workstream 3: coordinator browser cutover

Status: accepted.

## Task packet

### Outcome

Both frontend applications consume coordinator live state through the generated Hey API SSE
operation. A compact Zustand store retains current projections and connection state. The
coordinator no longer serves Socket.IO or carries its bespoke live-contract pipeline.

### Scope

- Build the smallest wrapper around the generated coordinator SSE operation that adds only missing
  lifecycle behavior. The pinned generated runtime retries thrown HTTP, network and read failures,
  but clean EOF and idle timeout require explicit handling.
- Treat the next complete snapshot after every connection as authoritative. Reconcile durable
  TanStack Query roots after that snapshot and invalidate precise roots for `resource.changed`.
- Replace the current coordinator Zustand store with current vehicle, engine, steering, buttons,
  lighting and health projections plus synchronization and connection error state.
- Remove boot IDs, topic revisions, protocol compatibility, resync decisions, trace and device
  registry from the store. Zustand is the reactive projection owner, not a transport facade.
- Validate every record through the generated Zod union before applying it. A malformed record
  surfaces an error and leaves the last valid projections unchanged.
- Move both applications' coordinator connection to the generated SSE operation.
- Remove the coordinator Socket.IO composition, publisher path, authorization tables, event map,
  schema, generators and generated live mappings after the frontend cutover passes.
- Preserve the local console-host Socket.IO path for Workstreams 4 and 5.

### Non-goals

- Do not put live projections into TanStack Query or create disabled queries as mutable stream
  containers. TanStack Query remains the owner of finite HTTP resources and mutations.
- Do not reimplement SSE parsing, validation or error retry already supplied by Hey API.
- Do not add a generic stream framework shared with the console host.
- Do not remove the shared Python or JavaScript Socket.IO dependencies while the console host still
  uses them.
- Do not restore any UI removed in Workstream 1.

### Initial ownership

This agent owns:

- `frontend/packages/coordinator-client/src/live/`, its package manifest and focused tests;
- coordinator-live startup and consumers in both frontend applications;
- coordinator Socket.IO composition and publication files under `hosts/src/e87canbus/api/`;
- `scripts/generate_live_contract.py`, `frontend/scripts/generate-live-contract.mjs`,
  `protocol/live-events-v1.schema.json` and coordinator generated live mappings;
- coordinator transport authorization and deployment tests; and
- coordinator-specific contract scripts in `frontend/package.json` while preserving the local
  console contract path.

Workstream 2 owns the accepted SSE event union and generated operation. Return a defect in those
seams to the orchestrator rather than changing it silently.

### Required seams

- The wrapper calls the generated Hey API operation directly and consumes its validated stream. It
  does not call `fetch`, `EventSource` or a handwritten parser.
- No event ID or `Last-Event-ID` behavior is added. The server sends no IDs and reconnection starts
  from a new snapshot.
- Many React consumers may select small projection values without copying them into another context
  or query cache.
- The console application continues using its separate local Socket.IO connection until Workstream
  5 while its coordinator connection uses SSE.

### Acceptance criteria

- Both applications start coordinator state from a generated and validated complete snapshot.
- Projection events replace one complete projection and notify only relevant selector consumers.
- Every initial snapshot reconciles durable roots. `resource.changed` invalidates the same roots as
  the old event.
- HTTP failure, network or read failure, idle timeout and clean EOF reconnect to a fresh snapshot.
- Malformed JSON or schema-invalid events fail visibly without replacing valid state.
- Strict Mode, route changes and repeated startup do not create duplicate connections.
- The coordinator serves no `/socket.io` path and imports no Socket.IO server.
- No coordinator live schema, bespoke generator, generated event mapping, protocol version or resync
  path remains.
- The local console-host Socket.IO stream still works.

### Targeted verification

Run from `frontend/`:

```text
pnpm api:check
pnpm --filter @e87canbus/coordinator-client test
pnpm --filter @e87canbus/coordinator-client typecheck
pnpm --filter @e87canbus/coordinator test
pnpm --filter @e87canbus/coordinator typecheck
pnpm --filter @e87canbus/coordinator build
pnpm --filter @e87canbus/console test
pnpm --filter @e87canbus/console typecheck
```

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_live_publication.py hosts/tests/test_transport_authorization.py hosts/tests/test_simulator_api.py hosts/tests/test_host_deployment.py hosts/tests/test_runtime_activation.py
uv run mypy
uv run ruff check hosts scripts/watch_frontend_contracts.py
git diff --check
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 3 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/03-coordinator-browser-cutover.md and the accepted Workstream 1 and 2 handoffs. Inspect the uncommitted diff and surrounding generated Hey API client, wrapper, Zustand store, both applications, coordinator composition, contract scripts and tests. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that the wrapper delegates parsing, validation and error retry to Hey API, covers clean EOF and idle timeout, keeps live state out of TanStack Query, avoids duplicate connections and completely removes coordinator Socket.IO machinery without breaking the local console stream." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 3 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/03-coordinator-browser-cutover.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `176802cca0576a633aa7cd49538917d5c4f26e20`
- Outcome: Both applications now consume the generated coordinator SSE operation into one compact
  Zustand projection store. Clean EOF and idle connections reconnect, every new snapshot
  reconciles durable query roots, and the coordinator no longer serves Socket.IO or carries its
  bespoke live contract.
- Files changed: Replaced the coordinator-client live store, transport, fixtures and focused tests;
  moved frontend consumers to generated OpenAPI types; removed the console dev proxy for
  coordinator Socket.IO; removed coordinator Socket.IO composition, publication, authorization,
  schema, generators, generated mappings and their tests; simplified shared live projection models
  and resource publication; updated package scripts, manifests, lockfile and affected tests.
- Decisions: The generated Hey API operation continues to own HTTP, network and read retry plus Zod
  validation. The wrapper adds a 25-second receive watchdog and clean-EOF reconnect loop, counts SSE
  comments as receive activity, and rejects the generated runtime's malformed-JSON string edge
  without changing retained projections. Each generated snapshot replaces all projections and
  reconciles durable roots. Projection events replace one field only. The console host's local
  `/console/socket.io` client, server, contract and dependencies remain unchanged.
- Verification: Every packet command passed. `api:check` passed; coordinator-client passed 7 files
  and 17 tests plus typecheck; coordinator passed 11 files and 38 tests plus typecheck and build;
  console passed 23 files and 100 tests plus typecheck. The selected backend suite passed 73 tests;
  mypy, Ruff and `git diff --check` passed. An additional 72 settings, button-profile, lifecycle and
  console-host tests passed, including all 9 local console Socket.IO tests.
- Known limitations or external checks: No manual browser session was run. The workflow's final
  local browser validation gate remains pending. The coordinator build retains its existing
  oversized-chunk warning.
- Specification drift: None.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: The reviewer reported Approve after contract, lifecycle, backend and generated-client
  checks. The orchestrator promoted one duplicate-connection defect to Required.
- Required findings: The module-local startup flag prevents duplicate calls only for one module
  instance. Vite hot replacement can dispose that instance without stopping its transport, then
  start a second coordinator stream from the replacement module. Add explicit hot-dispose cleanup
  and a focused lifecycle test.
- Optional observations: Remove the obsolete fixture boot-id argument and the unreachable profile
  id null check. Replace the computed Zustand projection assignment with an exhaustive typed update.
  Internal generated retries currently leave the badge disconnected rather than reconnecting. The
  generated runtime releases but does not cancel a reader after some mid-stream errors.
- Questions for orchestrator: The final browser gate already requires a long-running console SSE
  request through the configured origin, so it covers the proxy concern. Keep console contract
  script aliases and the stale SPA `socket.io` prefix for Workstream 6. Current documentation
  cleanup also remains with Workstream 6 as assigned.

## Resolution

- Finding dispositions: Promoted hot-reload duplication because acceptance forbids repeated startup
  from creating another connection. Accepted the fixture, resource-id and exhaustive store updates
  as direct simplifications. Deferred reconnecting badge wording and generated runtime reader
  behavior because they do not break convergence or retained state and the latter is generated
  dependency code.
- Simplification/deletion pass: The module singleton now owns one disposer used by both HMR and the
  focused lifecycle test; no second registry or environment branch was added. Removed the dead
  snapshot boot-id parameter and every call argument, removed the impossible profile-id null branch,
  and replaced the computed projection write with an exhaustive typed switch so generated event
  renames fail typecheck. Reconnect badge behavior, generated runtime code, documentation aliases
  and the SPA prefix remain unchanged as directed.
- Final verification: Every packet command passed after remediation. `api:check` passed;
  coordinator-client passed 8 files and 18 tests plus typecheck; coordinator passed 11 files and 38
  tests plus typecheck and build; console passed 23 files and 100 tests plus typecheck. The selected
  backend suite passed 73 tests; mypy, Ruff and `git diff --check` passed. The coordinator build
  retains its existing oversized-chunk warning.

## Closure review

- Verdict: Accepted. The focused reviewer confirmed hot disposal aborts the old stream, prevents
  stale post-abort writes and permits a single replacement connection. The accepted type and
  fixture simplifications also passed focused tests and typecheck.
- Remaining required findings: None.
- Accepted commit: `39ec49790c04344bb0dfff7e9c1561cb703e189b`
