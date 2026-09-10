# Workstream 6: Build provisionable coordinator and console images

Status: not started.

## Task packet

### Outcome

Both reusable images contain the same strict, idempotent first-boot consumer and their role-specific
Wi-Fi/TLS service composition. They contain no cloned host identity and remain fail-closed until a
valid bundle is fully installed.

### Scope

- Extend the image contract and manifest with provisioning version and storage limits.
- Remove reusable hostname, machine ID and SSH host keys; generate/install unique identity locally.
- Implement the root-owned durable first-boot phases, exact ZIP validation, bounded staging,
  ready-release activation, non-secret status and secret cleanup.
- Create `e87-admin`, `e87-kiosk` and service accounts with the specified login and sudo boundaries.
- Configure coordinator NetworkManager access point, DHCP-only dnsmasq, firewall, nginx HTTPS/mTLS
  and SSH exception.
- Configure console NetworkManager client, Chromium trust/client certificate and automatic
  certificate selection.
- Gate all role services on successful provisioning and remove the bundle/marker in the specified
  order.
- Add assembled-root or sandboxed behavioral tests for success, rejection and interrupted resume.

### Non-goals

- A second bundle schema, in-place repair, rollback, rotation or general-purpose installer.
- Internet sharing, DNS, gateway advertisement, IP forwarding, wireless CAN or cockpit behavior.
- A competing application authorization map in nginx.

### Initial ownership

- `images/` definitions, layers, role hooks, image checker and focused image tests
- Provisioning consumer, systemd, nginx, dnsmasq, NetworkManager, SSH, kiosk and service assets
  under `deploy/`
- Minimum host runtime configuration needed to use `/opt/e87canbus/current` and provisioned files,
  as an explicit integration exception coordinated with workstream 5

### Required seams

- Independently validate workstream 3's baked image contract and provisioning bundle.
- Install the authenticated-transport inputs defined by workstream 5 without broadening its
  authorization table.
- Preserve the accepted Docker builder and command from workstream 1.
- Produce both root and boot status documents consumed by workstream 7.

### Acceptance criteria

- Invalid, incompatible, corrupt, duplicate, unknown, traversal or oversized input changes no
  installed state and leaves role services disabled.
- Durable phases resume safely after interruption; `unprovisioned` clears only after complete
  validation, installation, cleanup and status.
- No secret value reaches status, journal or overly broad file permissions.
- First boot performs no package install, dependency resolution or application/frontend build.
- Each Pi receives its assigned hostname/device identity and locally unique machine ID/SSH keys.
- Coordinator and console implement the exact IP, DHCP, WPA3/PMF, no-forwarding, TLS and service
  policy from the Wi-Fi contract.
- Chromium can select only the installed console identity for the coordinator origin without
  frontend access to its private key.
- Both images build structurally through the existing wrapper; real hardware behavior remains
  explicitly owned by workstream 7.

### Targeted verification

```bash
uv run pytest e87ctl/tests/test_image_build.py hosts/tests/test_host_deployment.py -q
uv run ruff check e87ctl hosts
uv run mypy
bash -n e87ctl/scripts/build-pi-image deploy/bin/* deploy/kiosk/*.sh
bash -n images/*/customize.sh images/e87canbus-image-check
```

Run `systemd-analyze verify` in a suitable Linux/container fixture for all changed units. Validate
NetworkManager, nginx and dnsmasq configurations with their native parsers in the image test
environment where available. Do not claim Pi radio compatibility from these checks.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- State-machine phases and installed contract: `TBD`
- Verification: `TBD`
- Hardware behavior still owned by workstream 7: `TBD`
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
