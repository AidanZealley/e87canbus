# Workstream 2: Authenticate role-bearing devices

Status: not started.

## Task packet

### Outcome

The application can authenticate the three approved certificate roles. Device certificates produce
a `DEVICE` principal containing its closed role and canonical UUID, while every device
route remains closed because this workstream opens none.

### Scope

- Add `PrincipalKind.DEVICE` and carry `DeviceRole | None` on `Principal` without weakening the
  existing console and operator cases.
- Replace the console-only SAN classifier with one closed parser for `console`, `button-pad` and
  `servotronic-controller`.
- Parse the canonical hyphenated certificate role directly into the lean `DeviceRole` left by
  Slice 1.5. There is no legacy transport vocabulary to map or preserve.
- Put the authenticated principal on request state after authentication so later route handlers can
  use the identity established by middleware.
- Preserve loopback-only trust for verification and certificate headers, exactly one URI SAN,
  installation matching and canonical UUID-v4 checks.
- Extend authorization tests for valid devices, unknown roles, malformed identities, spoofed headers
  and the fact that authenticated devices still cannot access existing routes.

### Non-goals

- Device routes, request bodies, database rows, nginx changes or simulation certificates.
- A role registry, pluggable identity provider, generic claims object or certificate issuance.
- Changing Basic authentication, console privileges or the public liveness route.

### Initial ownership

- `hosts/src/e87canbus/api/auth.py`
- `hosts/tests/test_transport_authorization.py`

Integration exception: update a directly related auth test helper in another existing test file if
the `Principal` constructor changes. Do not touch route or persistence code.

### Required seams

- `Principal.kind` distinguishes device authority from console and operator authority.
- `Principal.role` is a `DeviceRole` only for device principals; `device_id` remains the
  canonical UUID string from the SAN.
- `request.state.principal` is assigned before `call_next` only after classification; handlers must
  not parse certificate headers again.
- `HTTP_PERMISSIONS` remains a closed table and does not yet admit `DEVICE` anywhere.

### Acceptance criteria

- Valid button-pad and Servotronic SANs produce device principals with the correct role and ID.
- A valid console SAN still produces the unchanged console principal.
- Unknown role, wrong installation, noncanonical UUID, multiple URI SANs, missing verification and
  non-loopback proxy headers remain unauthenticated.
- An authenticated device receives `403`, not console or operator access, for every existing
  protected route.
- Existing console, operator and CORS behavior remains unchanged.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_transport_authorization.py
uv run mypy
uv run ruff check hosts
uv run lint-imports
git diff --check
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 2 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/02-authenticate-role-bearing-devices.md, the accepted Slice 1.5 and Workstream 1 handoffs, linked source documents and relevant accepted ADRs. Inspect the uncommitted diff and surrounding authentication and authorization code. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check trusted-proxy handling, exact SAN cardinality, installation and canonical UUID validation, the closed certificate-role mapping, request-state identity, console/operator regressions and that no device route has been opened early. Confirm role identity does not recreate the deleted CAN device catalogue or registry." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 2 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/02-authenticate-role-bearing-devices.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking identity or authorization defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
