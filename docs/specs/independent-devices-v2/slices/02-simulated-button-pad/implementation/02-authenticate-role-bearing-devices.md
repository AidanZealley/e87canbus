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
- Introduce a lean closed `DeviceRole` at this certificate identity boundary. Parse the canonical
  hyphenated certificate role directly into it. There is no legacy transport vocabulary to map or
  preserve.
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

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 2 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/02-authenticate-role-bearing-devices.md, the accepted Slice 1.5 and Workstream 1 handoffs, linked source documents and relevant accepted ADRs. Inspect the uncommitted diff and surrounding authentication and authorization code. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check trusted-proxy handling, exact SAN cardinality, installation and canonical UUID validation, the closed certificate-role mapping, request-state identity, console/operator regressions and that no device route has been opened early. Confirm role identity does not recreate the deleted CAN device catalogue or registry.
```

Closure review:

```text
Perform the focused closure review for Workstream 2 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/02-authenticate-role-bearing-devices.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking identity or authorization defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `d38708dfd5a6fbcde4939af2749727d9d9077af8`
- Outcome: Verified button-pad and Servotronic certificates now produce `DEVICE` principals with a closed role and canonical UUID. The existing console certificate and operator Basic paths retain their principals. Middleware puts the classified principal on request state before an authorized handler runs. Device principals cannot access any existing protected route.
- Files changed: `hosts/src/e87canbus/api/auth.py`, `hosts/tests/test_transport_authorization.py`, and this handoff.
- Decisions: `DeviceRole` contains only the two canonical certificate role strings. The shared certificate parser keeps the existing loopback, verification, one-URI-SAN, installation and UUID checks. The liveness permission names its existing allowed kinds explicitly so adding `DEVICE` does not silently open it; the permission table has no device entry. No registry, claims wrapper or route was added.
- Verification: `uv run pytest -q hosts/tests/test_transport_authorization.py` passed (18 tests). `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports`, and `git diff --check` passed. The deletion and simplification pass found no obsolete classifier path or additional abstraction to remove.
- Known limitations or external checks: No external validation gate applies. Device routes belong to later workstreams.
- Specification drift: None.

## Independent review

- Reviewer: Fresh independent review agent.
- Verdict: Approved. The certificate parser accepts the three specified roles, and the closed permission table gives device principals no route access in this workstream.
- Required findings: None. `ApplicationAuthenticator` accepts certificate headers only from its trusted proxy addresses with `SUCCESS` verification; production defaults to loopback. It requires exactly one URI SAN, matches the installation ID, and accepts only a canonical UUID v4. The role parser maps `console` to the existing console principal and the two specified device strings to `DeviceRole`; unknown roles remain unauthenticated. Middleware sets `request.state.principal` after classification and before an allowed handler runs. `HTTP_PERMISSIONS` contains no `DEVICE` permission, including for liveness. The new role enum is confined to certificate identity and introduces no device catalogue or registry.
- Optional observations: None.
- Questions: None.

Review evidence: Compared the diff with the accepted Slice 1.5 and Workstream 1 handoffs, the Slice 02 and live/device API contracts, and ADR 0018. Production Uvicorn disables forwarded-header rewriting (`proxy_headers=False`), while nginx supplies verification and certificate headers. The targeted authorization suite passed (18 tests); `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports`, and `git diff --check` passed. Existing tests also exercised console and operator permissions, CORS preflight, and the browser live stream.

## Resolution

- Finding dispositions: The independent reviewer found no Required, Optional or Question items. No remediation was needed.
- Simplification/deletion pass: The implementation retains one certificate parser and the existing closed permission table. No obsolete console-only classifier or extra abstraction remains.
- Final verification: The implementation and independent review each ran the five targeted checks successfully. Closure review reran the authorization suite (18 passed) and `git diff --check`.

## Closure review

- Verdict: Approved. The independent review accepted no Required findings, so no remediation needed closure. The cumulative diff preserves trusted proxy and verification checks, exact URI SAN cardinality, installation and canonical UUID validation, and a closed mapping to the two device roles. Middleware exposes the classified principal before an authorized handler runs, while the permission table grants `DEVICE` no existing route.
- Remaining required findings: None. The focused authorization suite passed (18 tests), and `git diff --check` passed.
