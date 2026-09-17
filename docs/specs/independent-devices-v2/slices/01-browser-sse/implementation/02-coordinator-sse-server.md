# Workstream 2: coordinator SSE server and contract

Status: implementing.

## Task packet

### Outcome

The coordinator exposes the approved `GET /api/live` SSE endpoint beside its temporary Socket.IO
path. FastAPI models generate the event union, OpenAPI response and Hey API operation. Focused server
tests prove ordering, bounds, lifecycle and authorization before any browser switches transport.

### Scope

- Define the coordinator snapshot, complete projection and singular `resource.changed` event models
  in FastAPI. The union contains no trace or device-registry projection.
- Add `GET /api/live` with the approved content type, cache behavior, idle comments and one JSON data
  line per event.
- Implement atomic subscriber registration and initial snapshot capture, bounded per-subscriber
  pending output, slow-subscriber disconnection, nonblocking publication and clean shutdown.
- Preserve useful telemetry and health publication limits. Do not translate trace-specific rates,
  queues or diagnostics into SSE.
- Authorize the endpoint for console and operator principals through the HTTP permission table.
- Configure nginx buffering and read timeout for this endpoint without changing unrelated routes.
- Describe the actual event union under `text/event-stream` in the coordinator OpenAPI document and
  regenerate the Hey API operation, types and Zod validator.
- Verify the generated operation invokes the generated response validator for streamed JSON.
- Keep the coordinator Socket.IO path working unchanged for Workstream 3.

### Non-goals

- Do not change either frontend transport, Zustand store or application startup.
- Do not build a reconnect wrapper. Workstream 3 owns browser lifecycle.
- Do not remove old coordinator live schemas, generators, publisher or dependencies yet.
- Do not share a generic SSE publisher with the console host before its separate requirements are
  implemented.
- Do not add device HTTPS routes or change backend CAN simulation.

### Initial ownership

This agent owns:

- new coordinator SSE models, routes and publisher code under `hosts/src/e87canbus/api/`;
- required coordinator publisher configuration and diagnostics with focused tests;
- coordinator authorization entries and nginx behavior;
- `scripts/generate_openapi.py`, `protocol/openapi.json`, `frontend/openapi-ts.config.ts` and the
  generated coordinator HTTP client; and
- focused Python and generated-contract tests.

The old Socket.IO implementation remains owned by Workstream 3. Generated files belong here when
their OpenAPI source changes.

### Required seams

- Event names and shapes match the approved live API. Old envelopes are not reused inside SSE.
- The initial snapshot and subscriber registration form one operation. An update cannot fall between
  them.
- The controller owner offers changes without awaiting ASGI clients.
- `resource.changed` retains the precise settings and profile identities expected by existing query
  ownership.
- The generated operation exposes Hey API's SSE transport and generated Zod response validation for
  Workstream 3.

### Acceptance criteria

- An authorized subscriber receives one complete snapshot first, followed by complete changed
  projections and resource invalidations.
- Concurrent registration and publication cannot lose the first update.
- Keepalive comments arrive before the fixed client idle timeout recorded for Workstream 3.
- A saturated subscriber is disconnected without blocking publication or growing a queue.
- Disconnect and application shutdown release subscribers and tasks within a bound.
- Unauthorized principals cannot open the stream.
- OpenAPI represents the real event union as `text/event-stream`, and generated Zod validation runs
  for streamed JSON.
- The existing browser still works through Socket.IO at this intermediate commit.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_live_publication.py hosts/tests/test_transport_authorization.py hosts/tests/test_host_deployment.py hosts/tests/test_button_profile_api.py hosts/tests/test_settings_api.py hosts/tests/test_controller_loop.py
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm http:check
pnpm --filter @e87canbus/coordinator-client typecheck
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 2 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/02-coordinator-sse-server.md, the accepted Workstream 1 handoff and every source-of-truth document they link. Inspect the uncommitted diff and surrounding coordinator lifecycle, models, authorization, nginx config, OpenAPI output, generated Hey API operation and tests. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check event shapes, atomic initial snapshot semantics, bounded slow-client handling, nonblocking publication, keepalives, shutdown and generated Zod validation. Confirm the parallel Socket.IO path is temporary and unchanged." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 2 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/02-coordinator-sse-server.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `88b85e91a32952e18912e72b2aba561967c02d65`
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
