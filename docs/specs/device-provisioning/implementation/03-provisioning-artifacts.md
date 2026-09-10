# Workstream 3: Build and validate provisioning artifacts

Status: not started.

## Task packet

### Outcome

`e87ctl` can build validated coordinator and console ARM64 application bundles and exact
role-specific provisioning ZIPs from an image manifest and recovery package without writing a
disk.

### Scope

- Define strict v1 image-contract, application-manifest and provisioning-manifest models.
- Build role-specific ready-to-run virtual environments and frontend assets in a pinned ARM64
  Linux container.
- Publish manifest-backed `application-v1.tar.gz` artifacts in the specified ignored locations.
- Generate UUID device identities, role-constrained leaf certificates, hostnames and configuration.
- Create the exact provisioning ZIP entries for coordinator and console.
- Validate entry names, fields, roles, versions, sizes, digests, paths and storage reserves with
  bounded streaming reads.
- Add archive fixtures that prove rejection without relying only on source-string tests.

### Non-goals

- Installing artifacts on a Pi, writing removable media or implementing routine deploy/rollback.
- General archive extraction, arbitrary files, alternate compression formats or signing initial
  provisioning bundles.
- Adding the workstation package to the Pi application payload.

### Initial ownership

- Artifact, device-identity, application-build and bundle modules under `e87ctl/src/e87ctl/`
- ARM64 application-builder inputs under `e87ctl/`
- Focused tests and fixtures under `e87ctl/tests/`
- CLI wiring, package dependencies, `uv.lock` and artifact ignore rules as integration exceptions

### Required seams

- Consume the recovery types from workstream 2 without duplicating key parsing.
- Consume and extend the accepted image manifest contract used by workstream 1.
- Produce one fixed bundle contract that workstreams 4 and 6 both validate.
- Build output records dirty Git context but never requires a clean tree.

### Acceptance criteria

- Both role application archives are complete `linux-aarch64` releases with no first-boot build.
- The application archive cannot install outside its digest-named release directory.
- Leaf certificates have the exact URI SAN, EKU, validity rules and role binding.
- Both provisioning ZIPs contain exactly their allowed entries and complete per-entry digests.
- Duplicate, unknown, linked, traversal, oversized, corrupt and incompatible content fails before
  state changes.
- Private keys and passwords are absent from manifests, output, logs and generated frontend assets.
- The pinned build container and output provenance are explicit and tested without requiring Docker
  in the focused suite.

### Targeted verification

```bash
uv run pytest e87ctl/tests -q
uv run ruff check e87ctl
uv run mypy
cd frontend && pnpm api:check && pnpm build
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions and frozen schema versions: `TBD`
- Generated artifacts and provenance: `TBD`
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

