# Workstream 5: Role-image hardware acceptance

Status: not started.

## Task packet

### Outcome

The repository has a concise image build and inspection runbook, and recorded evidence shows that
both role images build on the M1 Pro, flash through Raspberry Pi Imager and boot on Raspberry Pi 4.

### Scope

- Add `images/README.md` with prerequisites, both build commands, output and manifest inspection,
  Raspberry Pi Imager steps, temporary access setup and exact per-role boot checks.
- State what a successful host-image boot proves and what later provisioning must still supply.
- Run the non-hardware integration checks before handoff.
- Give Aidan one checkpoint commit and collect results for both roles.
- Route each failure to the workstream that owns it. Record the correction and focused closure.
- Update stale image-building and deployment documentation within the approved feature boundary.

### Non-goals

Do not add an automated SD writer, provisioning CLI, application bundle, secrets, vehicle testing or
new image behavior merely to make the runbook easier.

### Initial ownership

- `images/README.md`
- Image-building references in `docs/setup.md` and `deploy/README.md`
- `hosts/tests/test_pi_image_build.py`, transferred from workstream 4
- This workstream record

Implementation defects return to workstreams 1 through 4. The orchestrator assigns exact file
ownership before any correction begins.

### Required seams

The runbook uses only the two public build commands and Raspberry Pi Imager. Temporary access must
not alter the reusable image or commit credentials. Generated artifacts stay outside Git.

### Acceptance criteria

- The runbook can be followed from a clean checkout on the M1 Pro.
- It names expected artifact and manifest locations without assuming a hard-coded build identifier.
- It has exact checks for OS, architecture, Pi model, role configuration and expected service state.
- Aidan records command outcomes, digests, flash results and Pi boot checks for both images.
- Failures are resolved and closed by their original owners.
- The final worktree contains no image, cache, credential or unrelated change.

### Targeted verification

```bash
uv run pytest \
  hosts/tests/test_pi_image_build.py \
  hosts/tests/test_host_deployment.py \
  hosts/tests/test_reliability.py
uv run ruff check \
  hosts/tests/test_pi_image_build.py \
  hosts/tests/test_host_deployment.py \
  hosts/tests/test_reliability.py
```

On the M1 Pro:

```bash
./scripts/build-pi-image coordinator
./scripts/build-pi-image console
```

On each Pi before role-specific checks:

```bash
uname -m
grep VERSION_CODENAME /etc/os-release
tr -d '\0' < /proc/device-tree/model
systemctl --failed --no-pager
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Verification: `TBD`
- Coordinator artifact, digest, flash and boot result: `TBD`
- Console artifact, digest, flash and boot result: `TBD`
- Corrections routed to prior owners: `TBD`
- Known limitations: `TBD`
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
