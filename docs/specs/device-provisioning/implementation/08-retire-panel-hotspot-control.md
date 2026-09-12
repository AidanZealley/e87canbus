# Workstream 8: Retire the panel hotspot control

Status: not started.

## Why this exists

The provisioned Wi-Fi network and the panel hotspot button control the same NetworkManager
connection. The access point now starts automatically and carries the console's only transport, so
the old maintenance-hotspot button can disconnect the console while the coordinator is running.
The hotspot display states also outrank `READY`, which prevents the healthy steady-state display
while the console remains associated.

Workstream 6 raised this conflict and deferred it. Aidan chose full removal in a separate Claude
thread on 2026-09-12 and confirmed that decision in the orchestration thread. The panel becomes a
status indicator with no network authority.

## Task packet

### Outcome

The coordinator panel shows `STARTING`, `READY`, `FAULT` and `OFF` only. It cannot start or stop
the provisioned Wi-Fi network. The obsolete hotspot helper, privileged host path, simulator and UI
operations, and firmware button event are absent.

### Scope

- Delete the host hotspot model and NetworkManager adapter with their focused tests.
- Reduce panel behavior to coordinator status and remove the hotspot dependency and button path
  from physical and simulated runners.
- Remove simulator API models and routes for hotspot state, connection, failure and panel presses.
  Regenerate the OpenAPI document and coordinator client rather than editing generated files.
- Remove hotspot controls and copy from the coordinator panel and simulator UI.
- Remove hotspot display states from coordinator-panel firmware. Keep the physical button wired
  and debounced, but stop emitting its UART event.
- Delete the root hotspot helper and sudo rule. Remove their image installation checks and restore
  `NoNewPrivileges=true` for the coordinator service.
- Update active panel, image and wiring documentation. Extend ADR 0013 to supersede the panel
  control in ADR 0010 while preserving accepted ADR history.
- Update the Wi-Fi specification so no panel action starts or stops the provisioned network.

### Non-goals

- Repurposing the physical button or reserving its UART command.
- Adding a console-link indicator or rebuilding one from wireless station polling.
- Changing access-point, DHCP, firewall, nginx or authorization behavior.
- Renaming hotspot-related comments that describe the provisioned access point rather than the
  removed control path.

### Initial ownership

- `hosts/src/e87canbus/{hotspot,panel}.py`, the NetworkManager hotspot adapter, panel runners and
  focused host tests
- Simulator panel API, `protocol/openapi.json` and generated coordinator-client output
- Coordinator panel and simulator frontend components and tests
- `devices/coordinator-panel/`
- Hotspot helper, sudo rule, coordinator service and coordinator image customization
- `docs/wiring.md`, `images/README.md`, `docs/specs/wifi-device-network.md` and ADR 0013

### Required seams

- Preserve the panel's heartbeat, fault, timeout and graceful-off behavior.
- Leave no host reader for a firmware event that is no longer emitted.
- Remove the controller service's last privileged network operation and its service-account sudo
  rule.
- Collapse the second panel thread if it exists only to isolate slow NetworkManager operations.
- Keep workstream 7 verification behavior and external-gate instructions synchronized with the
  final panel and image behavior.

### Acceptance criteria

- No coordinator code path can deactivate `e87canbus-coordinator-wifi`.
- `READY` is the steady-state panel display on a healthy provisioned coordinator.
- The image contains no hotspot helper or service-account sudo rule.
- Firmware emits no button event and the host has no handler for one.
- Simulator API, generated client and coordinator UI expose no hotspot operation or state.
- A service laptop can associate and reach HTTPS without physical panel action.
- ADR 0013 records retirement of ADR 0010's panel control without rewriting accepted history.
- Active documentation contains no instruction to press the panel button for Wi-Fi.

### Targeted verification

```bash
uv run pytest hosts/tests -q
uv run pytest e87ctl/tests/test_image_build.py e87ctl/tests/test_verify.py -q
uv run ruff check hosts e87ctl
uv run mypy
bash -n images/coordinator/customize.sh images/e87canbus-image-check deploy/bin/e87canbus-firewall
python3 -m py_compile deploy/bin/e87canbus-provision
```

```bash
cd frontend
pnpm api:generate
pnpm api:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Run the native coordinator-panel PlatformIO tests. Confirm generated diffs contain only the
removed hotspot operations. Docker image assembly, NetworkManager and physical Pi checks remain
external and must not be claimed on the implementation host.

## External validation

- Gate and placement: complete provisioned pair, after closure and before acceptance.
- Status: `Pending`
- Candidate and instructions: Assigned after closure. Use the procedure in workstream 7, updated
  for the status-only panel.
- Required evidence: All evidence listed in workstream 7 plus a healthy steady-state `READY`
  display and confirmation that panel presses do not change the provisioned network.
- Attempts and lasting decisions: `TBD`
- Resume condition: All workstream 7 and 8 physical evidence passes on one exact candidate.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Simplification pass: `TBD`
- Verification: `TBD`
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
