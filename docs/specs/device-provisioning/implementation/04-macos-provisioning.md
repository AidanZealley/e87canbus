# Workstream 4: Provision SD cards safely on macOS

Status: accepted.

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

- Gate and placement: macOS writer safety, after workstream 6 and before workstream 7.
- Status: `Testing`
- Candidate and instructions: The orchestrator records and pushes the combined workstream 4 and 6
  candidate `3bac67b68a265b10508effced7930ae6c82beef7`. On the M1 Pro MacBook, check out that
  exact commit and confirm it with `git rev-parse HEAD`. Record `sw_vers`,
  then run `uv sync --locked`. Keep the recovery package outside the checkout and use a compatible
  coordinator image manifest produced by the provisionable image builder.

  First capture the structured topology with `diskutil list -plist`, `diskutil apfs list -plist`
  and `diskutil info -plist /`. From those property lists, record the root volume's physical store,
  one internal whole disk, the spare card's whole external physical disk and one partition on that
  card.

  Set `E87_INSTALLATION` to the absolute recovery-package path, `E87_IMAGE` to the absolute image
  manifest path, `E87_SYSTEM_STORE` to the root volume's physical store, `E87_INTERNAL_DISK` to an
  internal whole-disk identifier and `E87_SPARE_PARTITION` to a partition identifier. Run these
  rejection checks. Each must exit nonzero before application build or disk mutation:

  ```bash
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_SYSTEM_STORE" --profile bench --confirm rejected --non-interactive
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_INTERNAL_DISK" --profile bench --confirm rejected --non-interactive
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_SPARE_PARTITION" --profile bench --confirm rejected --non-interactive
  ```

  Run the interactive command below, select the compatible image, spare whole disk and `bench`,
  and type the exact confirmation text containing its identifier, model and byte capacity. The
  spare card will be erased.

  ```bash
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION"
  ```

  Retain the secret-free final output and `diskutil` mount/unmount output. A zero exit proves the
  raw-device write, image-sized SHA-256 readback, exact boot-volume injection and ZIP readback all
  passed; the final output records all three artifact digests and says `First boot: pending`.
  Confirm `diskutil info "$E87_SPARE_DISK"` reports the whole disk unmounted after the command,
  where `E87_SPARE_DISK` is the selected whole-disk identifier.
- Required evidence: candidate hash and macOS version; discovery output; safe rejection of an
  internal disk, system-backing disk and partition; resolved spare-card identity; successful raw
  write; matching image-region readback; boot-only injection/readback; final unmount.
- Attempts and lasting decisions: No attempt yet. Aidan approved moving the gate after workstream 6
  because that stream produces the first truthful strict compatible image. Workstream 4 acceptance
  covers the reviewed writer implementation only and does not claim macOS or removable-media
  validation.
- Resume condition: all required evidence passes on the exact candidate, with no secret copied into
  the record.

## Implementation handoff

- Base commit: `2917f37baa7747f235d8fad94f98c76792e6563b`
- Outcome: Added the complete macOS card-preparation path. The CLI validates the caller-owned
  recovery package and selected image, confirms a resolved external physical disk, builds the
  current application and provisioning bundle, rechecks the disk identity, writes and verifies
  both artifacts and reports card preparation with first boot still pending.
- Files changed: Added `e87ctl/src/e87ctl/{macos,provision}.py`, recorded property-list fixtures and
  `e87ctl/tests/test_macos_provisioning.py`; extended `e87ctl/src/e87ctl/cli.py`; and updated this
  record and the plan status.
- Decisions: Discovery uses only `diskutil` property lists. It maps the root APFS volume or
  synthesized container to every physical store, considers only whole external physical disks
  eligible and accepts only exact `diskN` device identifiers as input. Confirmation binds the
  displayed identifier, model and byte capacity. A private validated-target type can be created
  only after the immediate full-identity recheck; the low-level writer has no string device-path
  input. The writer preflights artifact digests, unmounts the whole disk, lets `sudo dd` invoke
  macOS authentication, writes through `/dev/rdiskN`, hashes exactly the image-sized readback,
  mounts only the uniquely named `bootfs` partition, copies and syncs the ZIP, verifies its size
  and digest and finally unmounts the whole disk. Non-interactive mode requires `--image`, `--disk`,
  `--profile` and exact `--confirm` before discovery can lead to mutation. `--json` also requires
  non-interactive mode, so machine output never contains prompts.
- Verification: `uv run pytest e87ctl/tests -q` passed with 102 tests; `uv run ruff check e87ctl`,
  `uv run mypy` with 140 source files, both role-specific provision help commands and
  `git diff --check` passed. Fourteen focused tests use recorded list, APFS, root, internal,
  external, mounted and replacement property lists. Writer tests inject fake privileged and
  readback calls and never address a real device.
- Known limitations or external checks: No macOS command or real disk write ran in this Linux
  environment. The external gate remains pending after workstream 6 and before workstream 7.
- Specification drift: None in the implementation. Aidan approved the gate-placement correction;
  image validation remains strict.

## Independent review

- Reviewer: Claude Opus 5 (`claude-opus-5`) through the read-only review command, medium effort.
- Verdict: Changes required. The disk-protection and validated-writer design is sound, but the
  post-write boot-volume sequence can fail after destructive mutation and does not prove the
  boot-only mount criterion.
- Required findings: Query the boot partition before mounting and mount it only when absent,
  because DiskArbitration may already have mounted it after `dd`. Before copying the provisioning
  ZIP, use the existing disk mount enumeration to prove that the boot partition is the only mounted
  volume. The current unconditional mount may abort a successfully written card before injection.
- Optional observations: The post-copy free-space comparison duplicates bundle preflight and the
  validated-target token duplicates the private type and `isinstance` boundary. Cleanup currently
  hides an earlier failure if final unmount also fails. Full identity comparison includes benign
  mount changes; successful output reports pre-write mounts; filesystem ZIP readback may hit cache;
  and one `Path` takes a needless string round trip.
- Questions for orchestrator: Workstream 6 must explicitly preserve the `bootfs` partition label
  consumed by the exact-name writer. The provisionable-image gate-order conflict is real and not an
  implementation defect. Non-interactive success may require the caller to derive the exact
  confirmation string from `diskutil` before invoking the command.
- Verification: Claude ran the full 102-test e87ctl suite, Ruff, mypy over 140 source files, both
  relevant CLI checks and a read-only source/fixture audit on Linux. No macOS command or destructive
  operation ran.

## Resolution

- Finding dispositions: Accepted the required boot-mount finding. The writer now inspects `bootfs`
  before mounting it, tolerates DiskArbitration having mounted it already and enumerates the whole
  disk again to require `bootfs` as its only mounted partition before copying the ZIP. Added both
  requested focused cases. Accepted the optional deletion of the duplicate post-copy free-space
  comparison because completed-bundle validation against actual available space already enforces
  the reserve before copying. Accepted removal of the validated-target constructor token; the
  private type and writer `isinstance` boundary preserve the capability seam without duplicate
  machinery. Kept final-unmount failure as the surfaced error because an unexpectedly mounted card
  needs operator attention even if another failure preceded it. Kept the full identity comparison
  because a benign mount change fails safe before destruction. Kept pre-write mounts in the result
  because they describe the confirmed identity, and deferred questions about filesystem cache
  behavior to the real macOS gate. Retained the minor `Path` conversion and current bounded public
  error text because neither affects acceptance.
- Question dispositions: Workstream 6's task packet now freezes `bootfs` as the exact FAT boot
  partition label. Aidan resolved the compatible-image ordering conflict by moving the gate after
  workstream 6 and before workstream 7; validation stays strict. Non-interactive callers must
  derive the exact identifier, model and capacity confirmation from `diskutil`; adding a separate
  inspect command remains an explicit non-goal.
- Simplification/deletion pass: Removed the second boot-reserve comparison and constructor token.
  Reused one partition-mount enumeration for discovery reporting and the boot-only proof. Added no
  alternate mount path, cache-control mode or confirmation bypass.
- Final verification: `uv run pytest e87ctl/tests -q` passed with 104 tests; `uv run ruff check
  e87ctl`, `uv run mypy` with 140 source files, both provision help commands and `git diff --check`
  passed. The focused macOS module has 16 passing tests, including an already auto-mounted `bootfs`
  and rejection of a simultaneously mounted unexpected partition before ZIP copy.

## Closure review

- Verdict: Accepted for the external validation gate. The writer inspects `bootfs` before deciding
  whether to mount it, reuses an existing DiskArbitration mount and proves the whole disk's mounted
  partition map contains exactly that `bootfs` identifier and mount path before copying. The
  focused tests cover both automount and an extra mounted partition, including rejection before
  the ZIP appears. Removing the duplicate reserve comparison and constructor token leaves the
  pre-copy completed-bundle capacity validation and private validated-target writer boundary
  intact. No release-blocking defect was introduced by the remediation.
- Remaining required findings: None.
- Closure verification: `uv run pytest e87ctl/tests/test_macos_provisioning.py -q` passed (`16
  passed`); `uv run ruff check e87ctl/src/e87ctl/macos.py
  e87ctl/tests/test_macos_provisioning.py`; `uv run mypy` (`140 source files`); and `git diff
  --check` passed. The real macOS and removable-media checks remain at the documented external
  validation gate.
- Accepted commit: `3d01f300aee37d9cf0b3818143877083522c4374`
