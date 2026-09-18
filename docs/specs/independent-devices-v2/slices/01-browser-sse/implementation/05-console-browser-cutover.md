# Workstream 5: console browser cutover

Status: accepted.

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

- Base commit: `6d2135991f56de5c83c1f4a55bf56dd03683f475`
- Outcome: The console browser now consumes complete local CAN snapshots through the generated
  app-local Hey API SSE operation while retaining its accepted coordinator stream. The console
  host no longer serves Socket.IO or carries the old versioned live contract.
- Files changed: Replaced the local Socket.IO transport, versioned store, fixtures and focused tests
  with an app-local SSE lifecycle and complete projection store; added duplicate-start and HMR
  disposal coverage; split console development routing between direct coordinator requests and the
  same-origin console proxy; admitted the standard console Vite origins in simulator CORS; removed
  console-host Socket.IO composition, publication and tests; deleted the console live schema,
  Python and JavaScript generators, generated mapping and related package scripts.
- Decisions: The generated console operation owns HTTP, network and read retry, SSE parsing and Zod
  validation. The local wrapper adds only a 25-second receive watchdog, clean-EOF reconnect and the
  generated runtime's malformed-JSON string guard. It counts keepalive comments as receive
  activity, retains the last valid projection after errors, and replaces all local CAN state on
  each valid snapshot. Development sends coordinator HTTP and SSE directly to
  `http://127.0.0.1:8000`; same-origin `/api` and `/health` requests reach the console backend at
  `http://127.0.0.1:8001`. Shared Socket.IO dependencies and current documentation remain for
  Workstream 6.
- Verification: Every packet command passed. `api:check` passed; console passed 25 files and 102
  tests plus typecheck and build; coordinator-client passed 8 files and 18 tests plus typecheck.
  The selected backend suite passed 22 tests; mypy, Ruff and `git diff --check` passed. An expanded
  backend run passed 62 console, deployment and simulator API tests, including standard console
  origin CORS coverage.
- Known limitations or external checks: No manual browser session was run. The workflow's final
  local browser validation gate must confirm the two `/api/live` requests use distinct origins and
  remain open without proxy buffering. Repository-level Socket.IO dependencies and documentation
  cleanup remain assigned to Workstream 6.
- Specification drift: None.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: Approved. All packet criteria and verification commands passed.
- Required findings: None.
- Optional observations: The local store retains connection status/error fields that currently have
  no rendering consumer; its pending-state branch mirrors the coordinator store but is not reached
  by current paths. Generated retry backoff can extend worst-case reconnection. The SPA prefix and
  current documentation still contain Socket.IO remnants assigned to Workstream 6.
- Questions for orchestrator: The final browser gate remains the required proof that Vite streams
  both distinct-origin requests without buffering. Production builds are not ambiguous: the
  application builder sets `VITE_COORDINATOR_ORIGIN=https://10.42.0.1` for the console artifact.

## Resolution

- Finding dispositions: No Required findings and no remediation pass. Deferred the local connection
  state reduction because connection/error state is explicitly in scope and useful for final browser
  diagnostics. Deferred generated retry behavior, SPA prefix and documentation to their assigned
  dependency/cleanup work.
- Simplification/deletion pass: The implementation already removed the console Socket.IO server,
  client, schema, generators, generated mapping and protocol state. No further accepted change.
- Final verification: Independent review reran both frontend suites, API drift checks, build,
  typechecks, 62 backend tests, mypy, Ruff, import contracts, Prettier and `git diff --check`; all
  passed.
- Whole-feature correction: The local wrapper now limits each generated operation to one attempt and
  preserves its terminal HTTP or read error while the wrapper waits three seconds before opening a
  fresh stream. Focused tests cover initial fetch rejection and failure after a valid snapshot,
  including retained CAN state and recovery from the next complete snapshot. Console passed 25
  files and 104 tests plus typecheck and build; coordinator-client passed 8 files and 20 tests plus
  typecheck; `git diff --check` passed.

## Closure review

- Verdict: Accepted. With no remediation findings, the focused reviewer rechecked the generated
  operation seams, reconnect behavior, distinct origins, lifecycle guards, contract independence
  and scoped Socket.IO removal.
- Remaining required findings: None.
- Accepted commit: `82954b6d959a75402a67e38f37068b9f3c524a64`
