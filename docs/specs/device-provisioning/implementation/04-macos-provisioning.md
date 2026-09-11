# Workstream 4: Provision SD cards safely on macOS

Status: accepted.

## Task packet

### Outcome

On macOS, `e87ctl provision coordinator|console --installation <package>` safely resolves one
eligible SD card, builds the current application, writes and verifies a compatible image, injects
the provisioning ZIP and reports `first boot pending`.

### Scope

- Parse structured `diskutil` property-list output and resolve physical stores.
- Model a validated whole external physical disk, or the exact approved built-in removable Secure
  Digital case, as the only low-level writer input.
- Protect system-backing disks, internal disks outside that exact exception, partitions,
  unresolved selectors, changes in macOS-reported target identity and ambiguous targets.
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

- Every system-backing disk and every internal disk outside the exact approved built-in removable
  Secure Digital exception is rejected, including when explicitly requested.
- A partition, alias, glob, target with changed macOS-reported identity or unconfirmed action
  cannot reach the writer.
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
- Candidate and instructions: The orchestrator records and pushes the combined corrected
  candidate `aa5f0f3280f987ce2ffd669120e677e3f2b8a405`. On the M1 Pro MacBook, check out that
  exact commit and confirm it with `git rev-parse HEAD`. Record `sw_vers`,
  then run `uv sync --locked`. Keep the recovery package outside the checkout and use a compatible
  coordinator image manifest produced by the provisionable image builder.

  First capture the structured topology with `diskutil list -plist`, `diskutil apfs list -plist`
  and `diskutil info -plist /`. From those property lists, record the root volume, any synthesized
  container backing it, its physical-store partition and the whole physical disk containing that
  partition. Record the spare card's whole disk and one partition on that card. The spare card may
  be external or may use the approved built-in-reader case: a non-protected whole physical disk
  with `Internal`, `Removable`, `RemovableMedia` and `Ejectable` all true and `BusProtocol` exactly
  `Secure Digital`.

  Set `E87_INSTALLATION` to the absolute recovery-package path, `E87_IMAGE` to the absolute image
  manifest path, `E87_SYSTEM_DISK` to the whole physical disk containing the root physical store
  and `E87_SPARE_PARTITION` to a partition identifier. Set `E87_SPARE_DISK` to the spare card's
  whole-disk identifier. When the root uses a synthesized container, set `E87_ROOT_CONTAINER` to
  that whole container identifier. Do not set `E87_SYSTEM_DISK` to the physical-store partition
  itself.

  Run `diskutil info -plist "$E87_SPARE_DISK"` and retain the property list. This is the evidence
  source for `WholeDisk`, `VirtualOrPhysical`, `Internal`, `BusProtocol`, `Removable`,
  `RemovableMedia` and `Ejectable` when the built-in reader is used.

  Run these rejection checks. Each must exit nonzero before application build or disk mutation:

  ```bash
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_SYSTEM_DISK" --profile bench --confirm rejected --non-interactive
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_SPARE_PARTITION" --profile bench --confirm rejected --non-interactive
  ```

  When `E87_ROOT_CONTAINER` is present, also prove that the synthesized virtual whole disk is
  rejected:

  ```bash
  uv run e87ctl provision coordinator --installation "$E87_INSTALLATION" --image "$E87_IMAGE" --disk "$E87_ROOT_CONTAINER" --profile bench --confirm rejected --non-interactive
  ```

  If the topology has a separate internal, non-system whole disk that is not eligible removable
  Secure Digital media, run the same rejection command against it and record the result. Do not
  substitute a partition for that check. Most single-disk MacBooks have no such separate target;
  record that fact instead.

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
- Required evidence: candidate hash and macOS version; discovery output; safe rejection of the
  running-system whole disk and a partition; rejection of the synthesized root container when one
  exists; rejection of a separate ineligible internal whole disk when one exists; the spare-card
  `diskutil info -plist` output including every built-in-reader eligibility field when applicable;
  resolved spare-card identity; successful raw write; matching image-region readback; boot-only
  injection/readback; final unmount.
- Attempts and lasting decisions: Attempt 1 on 2026-09-11 failed on candidate `3bac67b` before any
  destructive operation; the card was not written to. Three blockers, recorded in full with measured
  evidence in `04-macos-provisioning-gate-attempt-1.md`. First, `SystemDiskutil.plist` appends
  `-plist` after the operand, which `diskutil` rejects, so every `provision` invocation aborts in
  `_system_physical_stores` before resolving any disk; the `disk3` and `disk0` rejection exits are
  therefore vacuous and must not be read as evidence that the internal or system-backing guards
  fired. Second, the MacBook Pro's built-in SDXC reader reports `Internal: true`, so the inserted
  card is ineligible by design and discovery lists no disks; the gate needs either a USB reader or a
  deliberate eligibility change. Third, the image builder's pinned `PACKAGE_SNAPSHOT_EPOCH` does not
  reach the snapshot generator, so both build attempts requested their own launch time and failed
  against an in-transition `trixie-security` suite, leaving no compatible manifest. Aidan approved
  the built-in MacBook reader as eligible only through the exact removable Secure Digital
  predicate recorded in the reopened correction below. The root physical store `disk0s2` is a
  partition, so attempt 2 uses its containing whole physical disk for the system-backing check and
  keeps partition rejection separate. Aidan previously approved
  moving the gate after workstream 6 because that stream produces the first truthful strict
  compatible image. Workstream 4 acceptance covers the reviewed writer implementation only and does
  not claim macOS or removable-media validation.
  Candidate `d0a22c1` contains the accepted writer and snapshot-propagation corrections and is ready
  for attempt 2.

  Attempt 2 on 2026-09-11 ran on candidate `d0a22c1` and failed with one blocker remaining; no
  destructive operation was attempted and the card was not written to. Full evidence is in
  `04-macos-provisioning-gate-attempt-2.md`. The `diskutil` argument-order and built-in-reader
  corrections are both confirmed against real hardware: discovery lists `disk4` as the only eligible
  disk, and the internal disk, synthesized container and both partitions are rejected. That
  correction also fixed a second latent defect attempt 1 could not reach, because `_read_whole_disk`
  read `Whole` where real `diskutil` emits `WholeDisk`. The snapshot-propagation fix is likewise
  confirmed: both repositories now resolve to the pinned `20260813T000000Z`. Correcting it exposed a
  defect it had been masking. The upstream sources template ends each stanza with
  `Options: check-valid-until=no`, which is one-line `sources.list` syntax and is silently ignored in
  a deb822 `.sources` file, so apt enforces the security archive's roughly one-week validity window
  and rejects the pinned snapshot as expired. Any pin older than that fails permanently until the
  deb822 `Check-Valid-Until: no` field is used instead. No compatible image manifest could therefore
  be produced, and the destructive path remains untested. Recorded as an observation rather than a
  blocker: Apple Silicon reports the internal SSD as `VirtualOrPhysical: Unknown`, so `disk0` is
  rejected by the media-type check before the protected-set comparison runs, even though
  `_system_physical_stores` correctly resolves it to `{'disk0'}`. Aidan stated he is not concerned
  about package drift between devices or full device installs and would accept reprovisioning every
  device if a version issue appeared, and does not want bloated code or blocked progress for it; the
  attempt 2 report recommends dropping the frozen historical pin and batching both role image builds
  instead.
  Aidan accepted target-package drift between devices and releases, including reprovisioning all
  devices if a package-version problem occurs. Workstream 1 therefore replaces the target image's
  historical snapshot layer with pinned upstream's rolling Trixie minbase layer and removes the
  epoch propagation and origin guard. It does not add the report's build-both suggestion or reorder
  the already-safe system-disk rejection for diagnostic wording.
  Candidate `aa5f0f3` contains that accepted rolling-layer correction and is ready for attempt 3.
  Attempt 3 on 2026-09-11 ran on exact candidate `aa5f0f3` and failed before disk mutation; the card
  was not unmounted or written. Full evidence is in
  `04-macos-provisioning-gate-attempt-3.md`. The rolling Trixie coordinator image now builds and all
  required unsafe selectors are rejected on real hardware. The interactive path then fails during
  the application build: production `tsc -b` includes `button-pad-renderer.test.ts`, whose
  repository-root protocol-vector import is absent because the application builder copies only
  `frontend` into its build tree. The gate remains blocked before the writer until the production
  frontend build receives that shared fixture or excludes test-only sources.
- Resume condition: correct the application build-context or production-TypeScript boundary exposed
  by attempt 3, record and push a new exact candidate, then obtain all required evidence without
  copying a secret into the record.

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

## Gate attempt 1 reopened correction

- Status: Accepted.
- Base commit: `47e9c59742f085de3ac65c4918cb161c9de45d5f`.
- Reopening reason: Attempt 1 found that real macOS `diskutil` rejects the command's trailing
  `-plist`, and Aidan approved a narrow change to the internal-media security boundary so the
  MacBook's built-in SD reader counts as an allowed reader. The candidate made no destructive
  change. The image snapshot blocker belongs to a separate image-builder correction.
- Scope: Place `-plist` after the complete one-token or `apfs list` two-token verb and before any
  operand. Permit an internal target only when it remains outside the protected system-store set,
  is a whole physical disk, uses protocol `Secure Digital` and reports `Removable`,
  `RemovableMedia` and `Ejectable` true. Preserve the existing external-media path and exact
  post-confirmation identity recheck. Clarify the gate's system-disk and partition inputs. This
  approved exception supersedes only the initial task packet's blanket internal-disk rejection and
  whole-external-disk wording.
- Changed files: `e87ctl/src/e87ctl/macos.py`, `e87ctl/src/e87ctl/provision.py`, the focused macOS
  test and one measured built-in reader fixture, the approved device-lifecycle specification, this
  record, the workflow README and `plan.md`.
- Decisions: The removable and ejectable properties are part of `DiskIdentity`, so the immediate
  recheck fails closed if any eligibility field changes. The protected-system check runs before
  the internal-media exception and has its own safe error. External whole physical disks stay
  eligible without requiring removable flags that existing `diskutil` fixtures do not report.
  The recorded fixtures and parser now use macOS's measured `WholeDisk` property rather than the
  synthetic `Whole` key, so the new built-in-reader fixture exercises the real property names.
- Verification: `uv run pytest e87ctl/tests -q` passed with 114 tests; `uv run ruff check e87ctl`
  passed; `uv run mypy` passed over 143 source files; both role-specific provision help commands
  returned usable output; and `git diff --check` passed. The focused macOS module has 26 passing
  tests.
- Simplification pass: One predicate owns both discovery and explicit-target media eligibility.
  The implementation adds no reader-name matching, bypass flag or alternate writer path.
- Specification drift: Approved. The product specification now records Aidan's exact built-in
  Secure Digital exception. All other internal disks remain rejected.
- Independent correction review:
  - Reviewer and verdict: Claude Opus through the read-only review command at medium effort;
    changes required.
  - Required finding 1: The measured built-in-reader property list has no card-level serial,
    media UUID or device-specific path, so the recheck can compare only the identity fields macOS
    reports.
  - Required finding 2: The original task packet still required a whole external disk and rejected
    every internal disk, contradicting Aidan's approved built-in-reader exception.
  - Optional observations: Say `no eligible disk` rather than `no eligible external disk`; add a
    gate rejection for the synthesized virtual root container; identify
    `diskutil info -plist "$E87_SPARE_DISK"` as the built-in eligibility evidence source; and mark
    built-in versus external media in the selection description.
  - Questions: Whether the attempt report reproduced the complete property list; whether the UI
    should label an eligible target as internal; and whether focused tests are sufficient evidence
    for an internal non-system rejection on a single-disk MacBook.
  - Verification: 114 e87ctl tests and 26 focused macOS tests passed. Ruff, mypy over 143 source
    files and `git diff --check` passed.
- Remediation triage and outcome:
  - Accepted required finding 2. The task packet now states the exact exception without changing
    its other safety criteria.
  - Rejected required finding 1 as non-blocking. A deliberate equal-capacity card swap during the
    seconds between confirmation and writing is outside the meaningful risk for this physically
    trusted provisioning path when macOS reports no identity difference. The criterion now says
    the writer detects changes in macOS-reported target identity, which the implementation
    rechecks in full. The focused changed-identity test remains.
  - Accepted every optional observation. The selection description labels `built-in removable
    media` or `external media`; the empty result says `no eligible disk`; and the gate now records
    the spare-disk property list and separately rejects a synthesized root container when present.
- Remediation verification: `uv run pytest e87ctl/tests/test_macos_provisioning.py -q` passed with
  27 tests and `uv run pytest e87ctl/tests -q` passed with 115 tests. `uv run ruff check e87ctl`,
  `uv run mypy` over 143 source files, both role-specific provision help commands and
  `git diff --check` passed.
- Remediation simplification pass: Kept one `DiskIdentity` and one comparison rather than adding a
  second identity source or reader-specific token. The two media labels are derived directly in
  the existing disk description. Removed the equal-reported-identity test after the orchestrator
  rejected that scenario as non-blocking. No new selector, bypass or writer path was added.

### Focused closure

- Verdict: Accepted for another macOS writer gate candidate. `SystemDiskutil` places `-plist`
  after either complete supported verb and before its operand. The exact built-in-reader exception
  remains subordinate to system-disk protection and requires a whole physical disk with protocol
  `Secure Digital` plus `Internal`, `Removable`, `RemovableMedia` and `Ejectable` all true.
  External physical disks retain their existing eligibility path. The parser and fixtures use the
  measured `WholeDisk` property.
- Finding outcomes: The task packet and product specification now describe the approved exception
  and the macOS-reported identity boundary without preserving the superseded blanket internal-disk
  rule. Discovery reports `no eligible disk`, and target descriptions distinguish built-in
  removable media from external media. The gate instructions use the root store's containing whole
  physical disk for system protection, keep partition rejection separate, reject a synthesized
  root container when present and retain the spare disk's eligibility property list. The
  orchestrator's equal-capacity, identical-reported-identity decision remains closed.
- Remaining required findings: None. The external gate remains in `Troubleshooting` until the
  corrected writer and image-builder changes pass on the exact macOS candidate.
- Closure verification: `uv run pytest e87ctl/tests/test_macos_provisioning.py -q` passed (`27
  passed`); targeted Ruff passed for `macos.py`, `provision.py` and the focused test; `uv run mypy`
  passed over 143 source files; and `git diff --check` passed.
- Accepted correction commit: `d93bf23afae5bbf1a3e8fed9ef16fe0ef454903e`. The implementation
  owner hit its usage limit after acceptance, so a fresh agent verified and committed the unchanged
  staged tree.
