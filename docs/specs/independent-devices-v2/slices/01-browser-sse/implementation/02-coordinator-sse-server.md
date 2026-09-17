# Workstream 2: coordinator SSE server and contract

Status: accepted; implementation commit pending.

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
- Outcome: Added the authorized coordinator `GET /api/live` stream beside Socket.IO. It sends a
  complete snapshot first, complete projection replacements, singular resource invalidations and
  idle comments through bounded independent subscriber output.
- Files changed: Added coordinator SSE models, publisher, route and focused tests; integrated its
  lifecycle and durable-resource publication; updated HTTP authorization and nginx; regenerated
  `protocol/openapi.json` and the coordinator Hey API types, operation and Zod schemas; added a
  generated-operation validation test.
- Decisions: Registration captures the snapshot while holding the same lock used to attach the
  subscriber. Controller offers retain one latest value per projection and never await a browser.
  Each subscriber uses the existing configured client capacity and disconnects on saturation. The
  keepalive interval is 15 seconds, with a 30-second nginx read timeout; Workstream 3's client idle
  timeout must remain above 15 seconds. SSE health omits Socket.IO and trace publisher diagnostics.
- Verification: All packet commands passed. The selected backend suite passed 95 tests. OpenAPI
  drift, mypy, Ruff, import contracts, `git diff --check`, HTTP contract drift and coordinator-client
  typecheck passed. The coordinator-client suite passed 7 files and 17 tests, including generated
  streamed-record Zod validation.
- Known limitations or external checks: No manual browser session was run. The existing browser
  remains on the unchanged Socket.IO path until Workstream 3, and the workflow's final local browser
  validation gate remains pending.
- Specification drift: None.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: The reviewer reported Approve after packet checks and live socket probes. The
  orchestrator promoted four findings that contradict acceptance criteria.
- Required findings: A subscriber can receive an older drained projection after its newer initial
  snapshot. Saturation removes a subscriber from accounting but does not close a request blocked in
  ASGI send. The served OpenAPI document retains an impossible `type: string` beside the event
  union even though the exported document patches it out. The generated `resource.changed` schema
  does not enforce settings-without-id and profiles-with-id.
- Optional observations: Simplify the unreachable deque `maxlen` and duplicate signal branches;
  avoid duplicated resource validation; consider exposing slow disconnects operationally. A
  stream opened during startup or shutdown may receive 200 before registration fails.
- Questions for orchestrator: Add a positive authenticated stream test. Keep the shared projection
  models in `api/models/live.py` through the migration, but update their Socket.IO-only description.
  The pre-existing models are projection definitions, not obsolete envelopes.

## Resolution

- Remediation ownership: The original implementation owner completed the promoted fixes and its
  verification before reaching its usage limit. A fresh replacement owner audited the complete
  cumulative diff, found that the slow-client test covered `stream_response` rather than Starlette's
  ASGI 2.3 task group, and finished the remediation by making the route register the outer request
  task for cancellation.
- Finding dispositions: Promoted stale-after-snapshot ordering and actual slow-request closure to
  Required because the approved contract promises atomic initial state and disconnection of slow
  clients. Promoted served/exported OpenAPI agreement because FastAPI models are the contract
  source. Promoted resource identity narrowing because generated validation must enforce the
  precise resource identities. Accepted the local simplifications and positive authorization test.
  Deferred new diagnostics fields and startup-window status behavior because neither blocks this
  migration seam.
- Simplification/deletion pass: Projection draining now enqueues under the registration lock, and
  one enqueue helper owns saturation. Removed the redundant deque `maxlen`, merged duplicate signal
  paths, replaced duplicated resource identity validation with a discriminated data union, removed
  the generated-document schema patch, and corrected the shared live-model description. The route
  now records the outer request task because Starlette drives ASGI 2.3 response bodies in a child
  task. No new diagnostics or startup compatibility behavior was added.
- Final verification: The replacement owner ran every packet command after its correction. The
  selected backend suite passed 98 tests. OpenAPI drift, mypy, Ruff, import contracts,
  `git diff --check`, HTTP contract drift and coordinator-client typecheck passed. The
  coordinator-client suite passed 7 files and 17 tests, including valid and invalid generated
  streamed-record validation. The three concurrency and cancellation tests also passed in 20
  consecutive runs.

## Closure review

- Verdict: Accepted. The focused reviewer confirmed all four promoted findings through code
  inspection, repeated concurrency tests, generated-client validation and a real authenticated ASGI
  probe through the authorization middleware.
- Remaining required findings: None.
- Accepted commit: `TBD`
