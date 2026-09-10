# Workstream 4: Provision SD cards safely on macOS

Status: not started.

## Task packet

### Outcome

On macOS, `e87ctl provision coordinator|console --installation <package>` safely resolves one
eligible SD card, builds the current application, writes and verifies a compatible image, injects
the provisioning ZIP and reports `first boot pending`.

### Scope

- Parse structured `diskutil` property-list output and resolve physical stores.
- Model a validated whole external physical disk as the only low-level writer input.
- Protect internal, system-backing, partition, unresolved, replaced and ambiguous targets.
- Support interactive selection and confirmation plus complete non-interactive inputs.
- Select and validate compatible local images and `car` or `bench` profiles.
- Compose workstream 3's application and provisioning artifact operations.
- Unmount, write through the raw device, hash the image-sized readback, mount only boot, copy and
  read back the ZIP, then unmount the whole disk.
- Emit secret-free human and versioned JSON preparation results.

### Non-goals

- Linux or Windows writers, bypass flags, direct arbitrary device paths or online first-boot
  claims.
- Persisted disk selections, device inventory or in-place repair.
- Pi-side bundle consumption or network verification.

### Initial ownership

- macOS discovery, validated-target, writer and provision orchestration modules under
  `e87ctl/src/e87ctl/`
- CLI wiring and focused fixtures/tests under `e87ctl/tests/`
- CLI documentation required to run the external gate

### Required seams

- The destructive writer accepts only a validated target created after the immediate identity
  recheck.
- Image and bundle validation comes from workstreams 1 and 3.
- Inputs containing secrets use protected files or standard input, never process arguments.
- `provision` reports card preparation separately from workstream 7's online verification.

### Acceptance criteria

- Every system-backing or internal disk is rejected, including when explicitly requested.
- A partition, alias, glob, changed target or unconfirmed action cannot reach the writer.
- The resolved disk identity shown for confirmation is the identity rechecked before writing.
- Successful writes verify the image-sized bytes and the completed boot ZIP.
- Only the boot partition is mounted for injection and the final whole disk is unmounted.
- Non-interactive mode fails before mutation if any required choice is absent.
- Output identifies role, hostname, device ID and artifact digests without exposing secrets or
  implying first-boot success.

### Targeted verification

```bash
uv run pytest e87ctl/tests -q
uv run ruff check e87ctl
uv run mypy
uv run e87ctl provision coordinator --help
uv run e87ctl provision console --help
```

Use recorded plist fixtures for APFS, synthesized, internal, external, partition, mounted and
identity-change cases. Do not invoke a real destructive writer from automated tests.

## External validation

- Gate and placement: macOS writer safety, after closure and before acceptance.
- Status: `Pending`
- Candidate and instructions: `TBD`
- Required evidence: candidate hash and macOS version; discovery output; safe rejection of an
  internal disk, system-backing disk and partition; resolved spare-card identity; successful raw
  write; matching image-region readback; boot-only injection/readback; final unmount.
- Attempts and lasting decisions: `TBD`
- Resume condition: all required evidence passes on the exact candidate, with no secret copied into
  the record.

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

