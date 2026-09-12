# Workstream 7: Verify the complete pair and cut over to provisioning

Status: implementing.

## Task packet

### Outcome

`e87ctl verify coordinator|console` reports the complete installed and online state, a newly built
and provisioned physical pair passes acceptance, and repository documentation exposes provisioning
as the sole coordinator-console setup path.

### Scope

- Implement versioned human and `--json` verification results with `passed`, `failed` and
  `unavailable` checks.
- Read the boot status offline and use trusted HTTPS plus key-only SSH for online checks as
  specified.
- Verify identity, bundle consumption, release, role services, Wi-Fi, mTLS, HTTP/Socket.IO
  authorization and operator-only rejection.
- Create exact checkpoint instructions and record MacBook, image, card and two-Pi evidence.
- Exercise one deliberately invalid bundle and confirm safe boot-partition failure reporting.
- Remove the superseded Ethernet runtime proxies and manual setup path from the hardware candidate.
- Update setup, deployment and image documentation, and add ADRs that supersede the named network
  decisions without rewriting accepted history.
- Run the final deletion and simplification pass across the assembled feature.

### Non-goals

- Routine deploy, rollback, repair, telemetry, rotation or additional device roles.
- Treating an offline/unavailable target as verified.
- Keeping compatibility aliases or Ethernet fallback after the accepted cutover.

### Initial ownership

- Verification and diagnostic modules plus tests under `e87ctl/`
- `docs/setup.md`, `deploy/README.md`, `images/README.md`, root `README.md` where relevant
- New superseding ADRs under `docs/decisions/`
- Obsolete Ethernet proxy, hotspot and manual setup assets after the external gate passes
- Small cross-layer corrections only through the orchestrator and original owning workstream

### Required seams

- Compare complete installation and device identities, not display prefixes.
- Reuse the public CA and management key in the recovery package without logging secrets.
- Treat preparation and online verification as separate result contracts.
- Preserve coordinator operation during console/Wi-Fi loss and prove no queued command replay.

### Acceptance criteria

- `verify` exits nonzero when a required check fails or is unavailable and never overclaims success.
- Human and JSON output cover the same versioned checks without secrets.
- A fresh physical pair passes every device-lifecycle and Wi-Fi acceptance criterion.
- The invalid-bundle card remains unprovisioned and exposes a useful bounded safe error on boot.
- The built image and application manifests, digests and candidate commit are recorded.
- Old coordinator-console Ethernet transport, proxies and setup instructions are absent after the
  replacement path passes.
- Documentation teaches the complete bare-card-to-connected-pair flow and compromise replacement.
- Repository-wide verification and final secret/artifact audits pass.

### Targeted verification

```bash
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run lint-imports
uv run python scripts/generate_custom_protocol.py --check
cd frontend && pnpm api:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build
bash -n e87ctl/scripts/build-pi-image deploy/bin/* deploy/kiosk/*.sh
bash -n images/*/customize.sh images/e87canbus-image-check
git diff --check
```

Adjust the shell glob only when an intentionally removed path no longer exists. Record rather than
hide any check unavailable on the implementation host.

## External validation

- Gate and placement: complete provisioned pair, after automated closure and before acceptance.
- Status: `Pending`
- Candidate and instructions: `TBD`
- Required evidence: candidate hash and clean/dirty build context; both image and application
  manifests/digests; MacBook builds; two safe SD writes/readbacks; coordinator and console first
  boot; unique hostname/machine ID/SSH keys; ZIP and staged-secret removal; marker transition;
  service health; exact IP/DHCP/no-forwarding behavior; WPA3-SAE and PMF; certificate trust and
  automatic console mTLS; HTTP and Socket.IO allowlists; laptop Wi-Fi-only denial; operator access;
  console rejection on operator status; Ethernet-disconnected operation; console disconnect/no
  replay/recovery; SSH-only service exception; and invalid-bundle boot status.
- Attempts and lasting decisions: `TBD`
- Resume condition: all required evidence passes on one recorded candidate. A WPA3/PMF failure may
  resume only after the single evidence-backed fallback allowed by the specification is approved
  and recorded as drift.

## Implementation handoff

- Base commit: `50e009c46a139e5b90f124195bdc917f8ec959f3`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Candidate and external instructions: `TBD`
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
