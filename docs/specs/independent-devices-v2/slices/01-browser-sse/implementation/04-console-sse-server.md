# Workstream 4: console SSE server and contract

Status: accepted.

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
- Outcome: Added the console host's separate same-origin `GET /api/live` stream beside the
  unchanged local Socket.IO path. It sends complete `console.snapshot` replacements through
  bounded subscriber output and has its own generated OpenAPI contract, Hey API operation, types
  and Zod validator.
- Files changed: Added the console SSE event model, publisher and focused tests under
  `hosts/src/e87canbus/console/` and `hosts/tests/console/`; integrated the route and lifecycle in
  `console/app.py`; added `scripts/generate_console_openapi.py`, `protocol/console-openapi.json`,
  the console app's Hey API config and generated `src/api/console-host/` client; added generated
  contract drift checking and streamed-record validation; updated frontend scripts, the console
  package's Zod dependency and the lockfile.
- Decisions: The console contract reuses only its local CAN projection model and imports no
  coordinator live type. The SSE publisher is console-specific: offers replace one complete pending
  snapshot, activity publishes at the existing one-second cadence, faults publish promptly, and
  each subscriber holds at most eight pending records. Per-subscriber revisions prevent a
  registration that captured newer service state from later receiving an older pending snapshot.
  Keepalives are sent after 15 idle seconds, so Workstream 5's local receive watchdog must exceed 15
  seconds. Publisher shutdown is bounded to one second and cancels stream requests, including ones
  blocked in ASGI send.
- Verification: Every packet command passed. The console backend suite passed 16 tests; mypy, Ruff,
  `git diff --check`, OpenAPI and generated-client drift checks, and console typecheck passed. The
  full console frontend suite passed 24 files and 101 tests, including generated streamed JSON Zod
  validation and the unchanged Socket.IO transport tests.
- Known limitations or external checks: No manual browser session was run. The browser remains on
  `/console/socket.io` until Workstream 5, and the workflow's final local browser validation gate
  remains pending.
- Specification drift: None.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: Changes requested. Publisher ordering, bounds, lifecycle and contract independence passed,
  but the generated event discriminator is weaker than the wire contract.
- Required findings: `ConsoleSnapshotEvent.type` has a model default, so OpenAPI omits it from the
  required fields and the generated TypeScript/Zod contract accepts records without a discriminator.
  Make `type` required at input, pass it explicitly when serializing, regenerate artifacts and add
  a negative validation assertion.
- Optional observations: Avoid redundant wakeups for already-pending non-urgent snapshots; leave
  the pre-existing optional CAN interface literal for later cleanup; keep the two small response
  classes independent; restore dependency ordering; avoid constructing an unused module-level app
  during contract generation; route-level first-record coverage could supplement publisher tests.
- Questions for orchestrator: Workstream 5 should use the proven 25-second watchdog, above the
  15-second keepalive. Its Vite routing tests and final browser gate must confirm the local SSE
  response streams without buffering.

## Resolution

- Finding dispositions: Accepted the Required discriminator fix because generated validation must
  match the actual event union. Accepted dependency ordering as mechanical cleanup. Deferred wakeup
  optimization, pre-existing CAN schema cleanup and extra route coverage because the current
  behavior is bounded and tested. Kept host-specific response classes as required by the approved
  direct-implementation boundary.
- Simplification/deletion pass: Removed the discriminator default instead of adding a validator or
  generated-client workaround. Serialization now supplies the one required literal explicitly.
  Restored alphabetical dependency ordering and left the deferred wakeup, CAN schema, response
  class and route-test observations unchanged.
- Final verification: Every packet command passed after regeneration. The console backend suite
  passed 16 tests; mypy, Ruff, `git diff --check`, OpenAPI and generated-client drift checks, and
  console typecheck passed. The full console frontend suite passed 24 files and 101 tests, including
  rejection of a streamed record without `type`.

## Closure review

- Verdict: Accepted. The generated Python, OpenAPI, TypeScript, Zod and SDK contracts all require
  the `console.snapshot` discriminator, and the focused negative validation test rejects its
  omission.
- Remaining required findings: None.
- Accepted commit: `8e64ab4e0868d8bdf1314fd7ce99e8f23daf0c04`
