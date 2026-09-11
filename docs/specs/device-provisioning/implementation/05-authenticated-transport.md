# Workstream 5: Enforce authenticated application transport

Status: accepted.

## Task packet

### Outcome

The coordinator application classifies unauthenticated, console and operator requests and enforces
the exact HTTP and Socket.IO allowlists. The console exposes disconnection and never replays a
command attempted while offline.

### Scope

- Add trusted-loopback identity ingestion for nginx-verified console certificates.
- Add HTTP Basic operator authentication backed by the provisioned Argon2id hash.
- Implement one executable route-to-permission table matching the Wi-Fi contract.
- Authenticate Socket.IO at connection time and authorize its exact send/receive events.
- Add external liveness and operator-only provisioning-status endpoints with minimal safe models.
- Update the console client for HTTPS, reconnect snapshots, visible disconnection and no command
  queueing.
- Regenerate and verify affected OpenAPI and live contracts.
- Keep authorization out of nginx and certificate/private-key handling out of frontend code.

### Non-goals

- Nginx configuration, certificate installation, Chromium policy or Wi-Fi configuration.
- JWTs, bearer tokens, request signing, multiple operators or simulator permissions for console.
- New product operations beyond the approved allowlists.

### Initial ownership

- Coordinator API, web and Socket.IO code under `hosts/src/e87canbus/`
- Relevant host tests under `hosts/tests/`
- Console frontend client, state and tests under `frontend/apps/console/`
- Generated HTTP/live contract inputs and outputs affected by those source changes

### Required seams

- Only a local trusted proxy may assert signed device identity. Direct remote header spoofing must
  not create a console principal.
- Console authorization uses the full installation/role/device identity established at connection.
- The provisioning-status response reads the non-secret status contract owned by workstream 6.
- Workstream 6 configures nginx and Chromium to supply these exact application inputs.

### Acceptance criteria

- Unauthenticated clients receive liveness only and no application data.
- The console can perform every listed production operation and no unlisted or simulator action.
- Wrong-installation and wrong-role identities fail; console fails on the operator-only endpoint.
- Correct operator credentials allow production and provisioning-status routes without storing the
  plaintext password on the coordinator.
- Socket.IO reconnects reauthenticate and recover a complete current snapshot.
- Offline console state is visible, local K-CAN remains available, and commands attempted offline
  are not replayed.
- Generated clients/contracts and focused authorization tests agree with the executable table.

### Targeted verification

```bash
uv run pytest hosts/tests/test_openapi_contract.py hosts/tests/test_socketio_server.py \
  hosts/tests/console -q
uv run ruff check hosts
uv run mypy
cd frontend
pnpm api:check
pnpm --filter @e87canbus/console typecheck
pnpm --filter @e87canbus/console test
```

Add focused route-table tests and run any narrower existing API tests touched by the final diff.

## Implementation handoff

- Base commit: `9c1ae9947e740ed086cca1265f6f862f4fc78d7f`
- Outcome: Added one shared authenticator for coordinator HTTP and Socket.IO traffic. Production
  startup reads the installed Argon2id operator hash and installation ID, trusted loopback proxy
  headers carry nginx-verified console certificates, and the application enforces the closed HTTP
  and live-event allowlists. The external liveness route is public. The strict provisioning-status
  route is operator-only. Console builds use the coordinator HTTPS origin and retain visible
  disconnect, reconnect snapshot recovery, local K-CAN state and immediate failure for offline
  mutations.
- Files changed: Added `hosts/src/e87canbus/api/auth.py`,
  `hosts/src/e87canbus/api/models/provisioning.py`,
  `hosts/src/e87canbus/api/routes/system.py` and
  `hosts/tests/test_transport_authorization.py`; updated coordinator API, live Socket.IO and CLI
  composition plus `hosts/tests/test_cli_main.py`; added host runtime dependencies in
  `pyproject.toml` and `uv.lock`; set the console application build origin in
  `e87ctl/application-builder/build-application` with its focused artifact test; regenerated
  `protocol/openapi.json` and the coordinator client's five generated HTTP files; and updated this
  record and the plan status.
- Authorization-table and generated-artifact decisions: Nginx supplies
  `X-E87-Client-Verify: SUCCESS` and the URL-escaped PEM client certificate in
  `X-E87-Client-Certificate`. HTTP reads the socket peer from the ASGI request. Socket.IO reads it
  from Engine.IO's preserved `asgi.scope`, never its synthetic `REMOTE_ADDR`. The application
  accepts device headers only from `127.0.0.1` or `::1`, parses the one signed URI SAN and requires
  its complete installation ID and `console` role. Uvicorn runs with proxy-header rewriting
  disabled, so an external `X-Forwarded-For` value cannot change the peer used for loopback trust.
  Verified device identity takes precedence over Basic credentials, so a wrong device identity
  cannot fall back to operator access. A request without a verified certificate may authenticate
  as the fixed `operator` user against the installed Argon2id hash. `HTTP_PERMISSIONS`,
  `SOCKET_SEND_PERMISSIONS` and `SOCKET_RECEIVE_PERMISSIONS` are the executable closed tables;
  focused tests compare them with every production OpenAPI operation and both live-contract enums.
  The status response is a bounded strict v1 model containing only the non-secret fields required
  by the product specification. Workstream 6 must write that exact model to
  `/var/lib/e87canbus-provisioning/status.json`, set `E87CANBUS_INSTALLATION_ID`, install the hash at
  `/etc/e87canbus/operator-password.hash`, configure nginx with these exact headers and preserve
  the locally served console origin in the coordinator's CORS inputs.
- Verification: `uv run pytest hosts/tests -q` passed with 852 tests. The final targeted Python
  run passed 49 tests. `uv run ruff check hosts
  e87ctl/src/e87ctl e87ctl/tests/test_provisioning_artifacts.py`, `uv run mypy` over 143 source
  files, builder shell syntax and `git diff --check` passed. `cd frontend && pnpm api:check`, the
  console typecheck and all 101 console tests passed. A production console build with
  `VITE_COORDINATOR_ORIGIN=https://10.42.0.1` passed and its compiled assets contain that origin.
- Known limitations or external checks: No nginx process, client-certificate handshake, installed
  first-boot status file or physical console ran in this environment. Workstreams 6 and 7 own that
  integration and hardware evidence. Docker and the full ARM64 application-bundle build did not
  run; the focused builder source and shell checks cover this stream's one build change.
- Specification drift: None.

## Independent review

- Reviewer: Claude Opus 5 (`claude-opus-5`) through the configured read-only review command at
  medium effort. The command exited successfully and edited no files.
- Verdict: Changes required. The closed authorization tables and identity formats match the
  approved contracts, but both HTTP and Socket.IO derive loopback trust from production values that
  do not represent the actual peer reliably.
- Required findings: `python-engineio` hardcodes `REMOTE_ADDR` to `127.0.0.1` in its ASGI adapter,
  so Socket.IO must read the peer from `environ["asgi.scope"]["client"]` and tests must exercise the
  real translated scope. Uvicorn enables trusted proxy-header rewriting by default; because nginx
  is the loopback peer, `X-Forwarded-For` can either replace the client with a remote address and
  reject the console or spoof loopback. Disable Uvicorn proxy headers for this loopback-only app.
- Optional observations: The receive-event table is a tested declaration rather than a runtime
  lookup; `request.state.principal` and the authorization preflight branch appear unused; the
  application-build role branch can be shorter; one test name is stale; a failed initial snapshot
  can leave a principal entry; and `deploy/README.md` still describes the Ethernet origin.
- Questions for orchestrator: Workstream 6 must preserve the console CORS origin when composing
  the rebuilt service. The coordinator SPA and static assets intentionally require operator Basic
  authentication because only liveness is public. Workstream 7 owns removal of the old Ethernet
  documentation and runtime path.
- Verification: Claude ran 32 focused host tests, Ruff and mypy over 143 source files; inspected the
  installed Engine.IO and Uvicorn middleware implementations; compared every HTTP and live-event
  permission with the approved contract; audited identity and status models, generated files,
  console offline behavior and locked dependencies. It did not run Docker, nginx, TLS hardware,
  frontend tests or API regeneration.

## Resolution

- Finding dispositions: Accepted both required findings. Socket.IO now derives peer trust from
  `environ["asgi.scope"]["client"]`; missing or malformed preserved scope fails closed. The focused
  test runs requests through Engine.IO's production ASGI translation and proves that its hardcoded
  loopback `REMOTE_ADDR` and a spoofed `X-Forwarded-For` cannot override the original peer. Both
  normal and reload Uvicorn paths set `proxy_headers=False`, and the CLI test inspects the resulting
  runtime configuration. Kept `SOCKET_RECEIVE_PERMISSIONS` as an explicit declared table because
  publishers can emit only after connection authentication and its enum-comparison test makes any
  newly added outbound event fail closed during verification. Recorded the console CORS seam for
  workstream 6. Deferred stale Ethernet documentation to workstream 7 as assigned by the plan.
- Simplification/deletion pass: Removed unused `request.state.principal` storage and the unreachable
  authorization preflight branch; the outer CORS middleware handles a focused unauthenticated
  preflight test before authorization. The application builder now conditionally exports only the
  console origin and uses one role-parameterized build command. Renamed the stale non-loopback CLI
  test. Socket.IO records a principal only after the initial complete snapshot succeeds, so a
  failed connection cannot leave an authorized session. Added no proxy settings, fallback address
  source or second authorization path.
- Final verification: `uv run pytest hosts/tests -q` passed with 853 tests. The focused auth, CLI,
  OpenAPI, Socket.IO and console-host run passed 29 tests. `uv run ruff check hosts
  e87ctl/src/e87ctl e87ctl/tests/test_provisioning_artifacts.py`, `uv run mypy` over 143 source
  files, application-builder shell syntax and `git diff --check` passed. `cd frontend && pnpm
  api:check`, the console typecheck and all 101 console tests passed.

## Closure review

- Verdict: Accepted. The remediation reads Socket.IO peer trust only from the preserved ASGI client,
  fails closed for absent or malformed scope and cannot be overridden by Engine.IO's synthetic
  `REMOTE_ADDR` or `X-Forwarded-For`. Both Uvicorn launch paths disable proxy-header rewriting.
- Remaining required findings: None. The accepted dead-state, preflight, builder-branch, test-name
  and principal-order simplifications introduce no release blocker. The workstream 6 handoff
  correctly requires its service composition to preserve the console CORS origin.
- Verification: The 45 focused transport, CLI and provisioning-artifact tests passed. Ruff, mypy
  over 143 source files, application-builder shell syntax, generated API checks, console typecheck,
  all 101 console tests and `git diff --check` passed.
- Accepted commit: `d896b526f66765219db2718bef81efb888f3f72e`
