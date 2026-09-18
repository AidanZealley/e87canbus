# Workstream 7: Run the simulated pad through the production API

Status: not started.

## Task packet

### Outcome

The named simulator runs one independent button pad as an authenticated in-process HTTPS-client
analogue. It consumes the production configuration handler, reports status and sends presses through
the production HTTP route without any project-device CAN traffic.

### Scope

- Add one simulation-only button-pad client that opens the production configuration handler through
  an in-process ASGI call, validates every complete envelope with the production model, retains the
  latest applied scene/generation and posts the approved status after applying it.
- Drive the endless configuration response with one small route-specific ASGI scope and
  send/receive loop. The installed `httpx2.ASGITransport` buffers until completion, so reserve it for
  finite status and press requests; do not create a general streaming transport replacement.
- Generate an ephemeral simulation certificate with the approved button-pad URI SAN and inject the
  same verified-proxy headers nginx supplies.
- Wrap only the client's private ASGI transport with the production `AuthorizationMiddleware` and a
  simulation authenticator. Do not enable an auth bypass or change the externally served simulator
  application's existing browser behavior.
- Route the existing development tap endpoint through the simulated client's one-shot press method.
  It posts exactly once to `/api/devices/button-pad/presses` and does not retry an ambiguous result.
- Start and stop the independent client in FastAPI lifespan after the production device publisher is
  ready. The accepted Slice 1.5 boundary leaves no alternative button-pad transport to select.
- Expose only enough immutable simulated-pad state for focused tests. Do not restore the deleted
  connected-device or topology UI.

### Non-goals

- Nginx, real TLS validation, Wi-Fi, flash persistence, CAN reception, button LED timing, firmware,
  admin diagnostics or a generic simulated-device framework.
- Simulating Servotronic over HTTP.
- Reintroducing frontend device controls, retrying presses or treating the SSE socket as presence.

### Initial ownership

- a new direct client under `hosts/src/e87canbus/runners/simulation/devices/`
- `hosts/src/e87canbus/api/main.py` and `api/internal/lifecycle.py` for client composition/lifecycle
- `hosts/src/e87canbus/deployment.py` and `runners/composition.py` only for direct client composition
- the button-pad development tap route and the smallest simulation command/runtime adjustments
- focused simulator, API lifecycle and deployment tests under `hosts/tests/`

Integration exception: update OpenAPI/generated artifacts only if an existing development route's
declared contract changes. Do not add frontend UI or alter the production device contract.

### Required seams

- The client parses bytes delivered by the actual SSE response and validates the JSON with the same
  envelope model hardware will follow. It does not call publisher or repository methods directly.
- The route-specific ASGI loop verifies the response status and headers, frames arbitrary body
  chunks correctly, supplies disconnect on shutdown and keeps a bounded handoff to the client. It is
  not exported as infrastructure for other streams.
- Its requests traverse the production certificate parser, route authorization, request models and
  handlers. The private wrapper exists solely because the local simulator intentionally serves its
  browser API without production authentication.
- The client posts status through HTTP after initial apply and each accepted replacement. Invalid
  envelopes leave the previous scene/generation active and post an error if that failure can be
  produced without bypassing server validation.
- A development tap invokes one client POST. The production handler supplies monotonic receipt time
  and the controller inbox owns kernel serialization.
- Startup waits for configuration publication availability; shutdown cancels the stream and closes
  the ASGI client before publishers and controller resources disappear.
- Default simulator button output is represented only by the independent scene. The removed virtual
  CAN peers, registry, ISO-TP programs and button-event traffic do not return.

### Acceptance criteria

- Simulator startup authenticates the fixed simulated identity and applies one complete initial
  scene through the production stream.
- A profile or application-state change updates the simulated scene without polling and produces a
  matching stored applied generation status.
- One development tap produces one HTTP press and one kernel intent evaluation, with no direct event
  injection and no retry.
- Restart reuses the durable configuration generation; reconnect does not increment it.
- The simulator has no project-device CAN peer or traffic and has no second path capable of
  delivering a press or scene.
- Client task failure and application shutdown release streams and tasks within a bound.
- Existing browser-facing simulator routes and frontend remain usable; no device UI is added.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_simulated_button_pad_client.py hosts/tests/test_simulator_api.py hosts/tests/test_simulation_runtime.py hosts/tests/test_deployment_profiles.py hosts/tests/test_controller_loop.py hosts/tests/test_device_configuration_service.py hosts/tests/test_device_configuration_route.py hosts/tests/test_device_api.py
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run from `frontend/` only if the development route schema changed:

```text
pnpm api:check
pnpm --filter @e87canbus/coordinator-client typecheck
```

The implementation agent creates `hosts/tests/test_simulated_button_pad_client.py` if it does not
yet exist.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 7 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/07-simulated-button-pad-client.md, all accepted dependency handoffs and linked product documents. Inspect the uncommitted diff and surrounding FastAPI lifespan, private ASGI transport, authentication middleware, simulation client, deployment composition and development tap route. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that every simulated config, status and press crosses production parsing and handlers; the private auth wrapper does not weaken the served app; status follows apply; presses are never retried; startup and shutdown are bounded; and no deleted CAN device peer, protocol or double-delivery path returns. Reject a generic simulated-device framework or restored device UI." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 7 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/07-simulated-button-pad-client.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking production-path, lifecycle, authentication or double-delivery defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
