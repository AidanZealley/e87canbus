# Workstream 2: Common host image

Status: not started.

## Task packet

### Outcome

Coordinator and console builds share one auditable host definition for stable OS packages,
runtimes, service ownership, filesystem layout and the later first-boot handoff.

### Scope

- Derive common requirements from `scripts/setup_host_common.sh`, both role setup scripts and
  existing `deploy/` assets.
- Add the smallest shared `rpi-image-gen` configuration needed by both hosts.
- Install stable runtime packages and create service users and directories with fixed ownership.
- Define the versioned image side of the first-boot handoff without defining final application,
  credential or secret bundle formats.
- Prevent package installation, dependency resolution and application builds on first boot.
- Add structural tests for shared contents and secret exclusions.

### Non-goals

Do not configure role-specific CAN, UART, hotspot, Ethernet, kiosk or application services. Do not
delete the current setup scripts, install a repository clone or create a generic image layer system.

### Initial ownership

- `images/common/**`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 1
- This workstream record

Changes to the builder or existing deployment assets require orchestrator approval and return to
their owner when practical.

### Required seams

Common files expose explicit inputs to the two role definitions. Existing files in `deploy/`
remain the source for runtime units, udev rules, helpers and kiosk scripts. Record any temporary
duplication with the legacy setup scripts.

### Acceptance criteria

- Both role definitions can consume one common definition without role conditionals spread through
  shared files.
- Common packages and filesystem state map to current setup behavior.
- No first-boot path runs `apt`, Git, `uv`, `pnpm` or frontend compilation.
- No key, password, user identity or final provisioning bundle format is embedded.
- Tests state the frozen first-boot boundary used by later role work.

### Targeted verification

```bash
bash -n scripts/build-pi-image
uv run pytest hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
uv run ruff check hosts/tests/test_pi_image_build.py hosts/tests/test_host_deployment.py
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Common package and filesystem decisions: `TBD`
- First-boot boundary: `TBD`
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
