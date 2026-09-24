# Workstream 6: Run the simulated pad through the production API

Status: accepted.

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
- This workstream proves the production path, not the transport. Workstream 5's route tests remain
  the authority on cancellation and slow-consumer disconnect; do not restate them through the
  hand-written loop, which could hide the defect they exist to catch.
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

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 6 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/06-simulated-button-pad-client.md, all accepted dependency handoffs and linked product documents. Inspect the uncommitted diff and surrounding FastAPI lifespan, private ASGI transport, authentication middleware, simulation client, deployment composition and development tap route. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that every simulated config, status and press crosses production parsing and handlers; the private auth wrapper does not weaken the served app; status follows apply; presses are never retried; startup and shutdown are bounded; and no deleted CAN device peer, protocol or double-delivery path returns. Reject a generic simulated-device framework or restored device UI.
```

Closure review:

```text
Perform the focused closure review for Workstream 6 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/06-simulated-button-pad-client.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking production-path, lifecycle, authentication or double-delivery defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `c3d995bc063d5f9367e3c90c114c979a627e4024` (accepted Workstream 5).
- Outcome: The simulator starts one authenticated in-process button pad, applies complete production SSE envelopes, reports its applied generation through the production status route, and sends each development tap through one production press request. It reconnects after stream failure, EOF or idle timeout and shuts down before the configuration publisher and controller.
- Files changed: Added `runners/simulation/devices/button_pad.py`, `runners/simulation/api/routes/button_pad.py` and `hosts/tests/test_simulated_button_pad_client.py`; changed `api/main.py`, `api/internal/lifecycle.py`, `runners/simulation/api/install.py`, `hosts/tests/test_device_configuration_service.py`, `protocol/openapi.json`, the generated coordinator client and this handoff.
- Decisions: The fixed simulated identity uses an ephemeral certificate and the existing trusted-proxy parser. Only the private client wraps the app with production authorization; the served simulator keeps its browser behavior. The worktree had no development tap route after Slice 1.5, so the new simulator-only `/api/dev/simulation/button-pad/tap` route accepts the existing press request model. A `simulate_button_pad=False` app-composition option keeps the direct configuration-service test isolated from the simulator's own subscriber. No CAN device peer or alternative scene and press path was added.
- Verification: The packet's targeted host suite passed (53 tests). OpenAPI drift check, mypy, Ruff, import contracts, frontend `api:check`, coordinator client typecheck and `git diff --check` passed. The deletion and simplification pass removed a redundant UUID conversion, shared the lifespan client reference and kept the stream loop private to this client.
- Known limitations or external checks: The simulated certificate proves application parsing and authorization, not nginx TLS verification. TLS, Wi-Fi and hardware checks are outside this slice.
- Specification drift: None.

## Independent review

- Reviewer: Independent review agent.
- Verdict: Approved. The simulated pad uses the production configuration, status and press handlers, and its private authentication wrapper leaves the served simulator app unchanged.
- Required findings: None. The stream request passes through `AuthorizationMiddleware`, certificate classification, role authorization and the production configuration route. The client parses complete SSE records with `ButtonPadConfigurationEnvelope`, applies each valid scene, then posts its generation through the production status route. The development tap makes one HTTP press request, which the production handler stamps and submits through the controller inbox; the client has no press retry or direct kernel injection. The stream task starts after the configuration publisher and stops before the publisher and controller. Startup and stream cleanup use finite waits. The simulator session still creates only vehicle and Pi CAN endpoints, with no button-pad peer, device protocol or second delivery path.
- Optional observations: The tap route is installed for every `FULL` simulation API, but `create_app(simulate_button_pad=False)` or a supplied authenticator leaves `app.state.simulated_button_pad` as `None`. Calling the tap route in those compositions raises an attribute error instead of returning its declared 503 (`runners/simulation/api/install.py`, `api/main.py`, `runners/simulation/api/routes/button_pad.py`). Normal simulator composition always creates the client, so this does not block the slice. A small availability guard would make the route match its declared error response.
- Questions: None.

Review evidence: Read the accepted Workstream 1 through 5 handoffs and linked device contracts. Inspected the uncommitted diff, lifespan, authorization middleware, device handlers, stream service, simulation session and development route. The targeted host suite passed (53 tests); OpenAPI drift, mypy, Ruff, import contracts and `git diff --check` passed. No frontend device UI was added, and the generated client change is limited to the new development tap operation.

## Resolution

- Finding dispositions: No Required findings. Defer the optional disabled-client tap guard. The production simulator always composes the client; the disabled option exists only to isolate an existing configuration-service test, and no approved behavior depends on tapping that test composition.
- Simplification/deletion pass: Reviewed the client, lifespan and route for duplicate scene or press paths, reusable streaming infrastructure and restored CAN device code. None remain. The implementation agent removed a redundant UUID conversion and kept the route-specific stream loop private.
- Final verification: The implementation and independent review each ran the 53 targeted host tests, OpenAPI drift check, mypy, Ruff, import contracts and `git diff --check`. The implementation also ran frontend `api:check` and coordinator client typecheck for the new development route.

## Closure review

- Verdict: Approved. The independent review accepted no Required findings. The current diff has no release-blocking production-path, lifecycle, authentication or double-delivery defect.
- Remaining required findings: None. The private client alone wraps the app with `AuthorizationMiddleware`; configuration, status and press requests reach the production routes. The lifespan starts the client after configuration publication and stops it before publisher and controller teardown. The tap sends one HTTP press with no retry or direct kernel submission. Focused simulator tests passed (8 tests), and `git diff --check` passed.
