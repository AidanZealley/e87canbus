# Workstream 5: console browser cutover

Status: not started.

## Task packet

### Outcome

The console browser consumes its local CAN projection through the generated console-host Hey API SSE
operation while retaining its accepted coordinator SSE connection. The two `/api/live` streams use
distinct origins. The console host no longer serves Socket.IO or carries a bespoke live contract.

### Scope

- Add the smallest local lifecycle wrapper around the generated console SSE operation. Delegate
  parsing, JSON validation and thrown-error retry to Hey API. Add clean-EOF and idle-timeout
  reconnection where the pinned generated runtime lacks them.
- Retain only the complete local CAN projection and connection state. Keep the existing small
  Zustand store if it remains the most direct reactive owner; do not move stream state into TanStack
  Query or add another general state layer.
- Update development routing so local `/api/live` reaches the console backend while coordinator API
  and coordinator SSE requests use `COORDINATOR_ORIGIN`.
- Make the standard repository development commands work without operator-supplied CORS flags.
- Remove the console host's Socket.IO composition, local browser client, schema, Python and
  JavaScript generators, generated mapping and protocol-version behavior after cutover.
- Preserve the accepted coordinator stream without importing its types into local state.

### Non-goals

- Do not change coordinator event shapes, reconnect behavior or Zustand projections.
- Do not combine local and coordinator streams under one generated client or one event union.
- Do not create a generic multi-origin transport manager.
- Do not remove shared Socket.IO dependencies or final documentation remnants. Workstream 6 owns the
  repository-wide deletion after confirming no live consumer remains.
- Do not change CAN receiver semantics.

### Initial ownership

This agent owns:

- `frontend/apps/console/src/local-live/`, console application startup and focused consumers;
- console Vite configuration, development environment and focused routing tests;
- console-host Socket.IO code under `hosts/src/e87canbus/console/`;
- `scripts/generate_console_live_contract.py`, `protocol/console-live-v1.schema.json`, the console
  JavaScript live generator and generated mapping; and
- host and frontend tests that directly encode the retired local transport.

Workstream 4 owns the accepted console event model and generated operation. Contract corrections go
through the orchestrator.

### Required seams

- The local wrapper calls the generated console Hey API operation directly. It does not use
  `fetch`, `EventSource` or a handwritten SSE parser.
- The console frontend holds one coordinator stream at the configured coordinator origin and one
  local stream at its serving origin.
- The local snapshot replaces the complete local projection. It has no protocol version, replay
  state or dependency on coordinator boot state.
- Standard local startup remains the three commands documented in the repository root.

### Acceptance criteria

- The local UI starts from a generated and validated complete `console.snapshot`.
- Local HTTP failure, network or read failure, idle timeout and clean EOF reconnect to a fresh
  snapshot.
- A malformed local event reports an error without replacing the last valid CAN projection.
- Strict Mode, route changes and repeated startup do not duplicate either stream.
- In development, Network tools show distinct coordinator and local `/api/live` requests with no
  proxy collision.
- The console host no longer serves `/console/socket.io` or imports Socket.IO.
- No console live schema, bespoke generator, generated event mapping or protocol-version path
  remains.
- The coordinator stream and all finite coordinator HTTP operations still work from the console UI.

### Targeted verification

Run from `frontend/`:

```text
pnpm api:check
pnpm --filter @e87canbus/console test
pnpm --filter @e87canbus/console typecheck
pnpm --filter @e87canbus/console build
pnpm --filter @e87canbus/coordinator-client test
pnpm --filter @e87canbus/coordinator-client typecheck
```

Run from the repository root:

```text
uv run pytest -q hosts/tests/console hosts/tests/test_host_deployment.py
uv run mypy
uv run ruff check hosts scripts/watch_frontend_contracts.py
git diff --check
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 5 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/05-console-browser-cutover.md and all accepted dependency handoffs. Inspect the uncommitted diff and surrounding generated local client, wrapper, local state, Vite routing, console host composition, contract scripts and tests. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check direct use of the generated Hey API operation, clean EOF and idle timeout handling, distinct origins, duplicate-connection prevention, contract independence and complete removal of the console Socket.IO path without changing the coordinator stream." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 5 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/05-console-browser-cutover.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
