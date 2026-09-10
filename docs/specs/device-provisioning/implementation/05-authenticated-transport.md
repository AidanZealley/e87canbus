# Workstream 5: Enforce authenticated application transport

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Authorization-table and generated-artifact decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (use the review command in `README.md`)
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
