# Workstream 2: build and verify firmware artifacts

Status: not started.

## Task packet

### Outcome

`uv run e87ctl firmware build button-pad` invokes the checked-in PlatformIO project and emits a
secret-free, self-verifying manifest with every image needed for physical flashing.

### Scope

- Add the button-pad target to `e87ctl`'s small supported-firmware table. Keep it independent of
  the host package.
- Invoke PlatformIO without recreating its build system in Python. Emit bootloader, partition
  table, application and any other required first-flash image with fixed offsets.
- Record manifest format, target, chip, build environment, UTC build time, Git commit and dirty
  flag, provisioning-interface version, identity partition offset and maximum size. For each image
  record filename, offset, byte length and SHA-256.
- Validate all fields, bounded file reads, digest, size, overlap, flash bounds and partition
  consistency before an artifact is accepted. A later flash must be able to revalidate the same
  artifact without a rebuild.

### Non-goals

Board connection, writing flash, certificate issuance, firmware upload to the coordinator, or
generic support for hypothetical firmware targets.

### Initial ownership

`e87ctl/src/e87ctl/`, `e87ctl/tests/`, `e87ctl/pyproject.toml`, relevant lockfile and build
documentation. Touch `devices/button-pad/platformio.ini` only for a documented build integration
fix; the Workstream 1 partition contract is frozen.

### Required seams

Consume Workstream 1's actual PlatformIO images and checked-in partition table. Expose one
validated manifest to Workstream 3. Keep ordinary reflash images separate from identity and
configuration partition data.

### Acceptance criteria

- The specified command builds the project and emits one manifest plus all required flash images.
- A manifest and unchanged images validate on repeated reads; no secrets appear in them.
- Wrong chip, target, flash size, changed digest, length, overlap, offset or out-of-range image
  is rejected before any flash operation can use it.
- The identity offset and capacity agree with the checked-in table. No host-package import appears
  in `e87ctl`.

### Targeted verification

Run `uv run pytest -q e87ctl/tests`, `uv run ruff check e87ctl`, `uv run mypy`, and the new
`uv run e87ctl firmware build button-pad` command. Keep the manifest artifact outside the source
tree or ignored. Tests should cover actual malformed artifact boundaries, not every parser branch.

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
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
