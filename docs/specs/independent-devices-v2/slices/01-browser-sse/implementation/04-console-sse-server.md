# Workstream 4: console SSE server and contract

Status: implementing.

## Task packet

### Outcome

The console host exposes its own same-origin `GET /api/live` SSE endpoint beside the temporary local
Socket.IO path. Its FastAPI model generates a separate OpenAPI document, Hey API operation and Zod
validator. Focused tests prove local stream behavior without involving the coordinator union.

### Scope

- Define the complete `console.snapshot` event and local CAN projection in the console host.
- Add same-origin `GET /api/live` with the approved framing, cache behavior and idle comments.
- Implement atomic initial snapshot registration, bounded pending output, slow-subscriber
  disconnection, nonblocking offers from the CAN receiver and bounded shutdown.
- Generate and check a console-host OpenAPI document and app-local Hey API client with Zod response
  validation.
- Verify the generated console operation validates streamed JSON.
- Keep `/console/socket.io` and the current local browser transport working for Workstream 5.
- Record the local idle timeout and keepalive relationship for the next workstream.

### Non-goals

- Do not import coordinator event models, generated clients, stores or query ownership.
- Do not change the console browser transport or development proxy yet.
- Do not remove the console live schema, generators or Socket.IO dependencies yet.
- Do not introduce a configurable or generic publisher shared with the coordinator solely to remove
  a small amount of direct code.
- Do not alter CAN receiver behavior.

### Initial ownership

This agent owns:

- new console SSE models, route and publisher code under `hosts/src/e87canbus/console/`;
- focused console host tests;
- a new console OpenAPI generation script and generated document;
- the console app's Hey API generation configuration and generated local client; and
- contract scripts only as needed to generate and check both accepted OpenAPI documents.

The old console Socket.IO implementation remains owned by Workstream 5. The accepted coordinator
contract and client are read-only dependencies.

### Required seams

- The console-host event union remains separate even if its framing matches the coordinator stream.
- The CAN receiver offers complete latest snapshots without waiting on a browser.
- The generated local operation and validator live with the console application and do not enter the
  coordinator-client package.
- Both hosts may use `/api/live` because they have distinct origins. Workstream 5 owns development
  routing that makes those origins explicit.

### Acceptance criteria

- A subscriber receives a complete `console.snapshot` first and after each new connection.
- CAN activity and fault changes publish a complete replacement at the existing bounded cadence.
- Concurrent registration and publication cannot lose the first change.
- Idle comments, queue bounds, slow-subscriber disconnection and shutdown have focused tests.
- The console OpenAPI document describes the actual `text/event-stream` event schema.
- Streamed JSON passes through the generated console Zod validator.
- No console event model imports a coordinator live type.
- The existing local browser still works through `/console/socket.io` at this intermediate commit.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/console
uv run mypy
uv run ruff check hosts scripts
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm --filter @e87canbus/console typecheck
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 4 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/04-console-sse-server.md and all accepted dependency handoffs. Inspect the uncommitted diff and surrounding console service lifecycle, event models, separate OpenAPI generation, generated local Hey API client and tests. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check contract independence, atomic initial snapshots, nonblocking CAN offers, bounds, keepalives, shutdown and generated validation. Confirm the local Socket.IO path is temporary and unchanged." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 4 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/04-console-sse-server.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `f5fcfe357e26eb178c9db8fc903db955f2167b75`
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
