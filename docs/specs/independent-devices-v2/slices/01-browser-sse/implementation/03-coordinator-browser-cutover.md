# Workstream 3: coordinator browser cutover

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (Claude command used, or the recorded fresh-session fallback)
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
