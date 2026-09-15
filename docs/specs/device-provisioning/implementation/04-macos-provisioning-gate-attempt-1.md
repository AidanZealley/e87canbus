# Workstream 4 external validation — attempt 1 report

**Verdict: FAILED. Gate cannot proceed on this candidate.**
Three blockers, two of which are defects in the candidate itself. No destructive
operation was attempted; the SD card was not written to, mounted, unmounted or
modified in any way.

---

## 1. Environment

| Item | Value |
|---|---|
| Candidate commit | `3bac67b68a265b10508effced7930ae6c82beef7` (verified with `git rev-parse HEAD`) |
| Working tree | clean, detached HEAD |
| Host | MacBook Pro, Apple M1 Pro |
| `sw_vers` | ProductName macOS, ProductVersion **26.6**, BuildVersion **25G70** |
| `uname -m` | `arm64` |
| uv | 0.11.11 (Homebrew), `uv sync --locked` completed clean |
| Docker | Docker Desktop 20.10.14, daemon up, native aarch64 |

Note on the branch: the branch tip was one commit ahead at `1b7905a`
("Record provisionable image acceptance"). That commit touches only three
specification markdown files and no code, so the candidate is code-identical to
the branch tip. Validation was performed on `3bac67b` as instructed.

### Targeted verification on real macOS (all passed)

```
uv run pytest e87ctl/tests -q      -> 104 passed
uv run ruff check e87ctl           -> All checks passed
uv run e87ctl provision coordinator --help   -> OK
uv run e87ctl provision console --help       -> OK
```

### Caller-owned inputs

Recovery package created outside the checkout at
`~/e87-installation/gate-w4.json` (mode 0600, CA sidecar `gate-w4-ca.pem` mode
0644), installation ID
`rfn2pld32n2lmlia4o7k2qa4bhjfj3ipiqpiio6ksxnnblbdyelq`. No secret material is
reproduced in this report.

### Recorded topology

`diskutil list -plist`, `diskutil apfs list -plist` and `diskutil info -plist /`
were captured. Resolved structure:

- Root volume `disk3s1s1`, `ParentWholeDisk` `disk3`
- APFS containers: `disk1` <- `disk0s1`, `disk2` <- `disk0s3`, `disk3` <- `disk0s2`
- Root volume's physical store: **`disk0s2`**
- Internal whole disk: **`disk0`** (500.3 GB, the only internal physical disk)
- SD card: **`disk4`** — see blocker 2
- Card partitions: `disk4s1` (`BOOT`, Windows_FAT_32, 109.1 MB), `disk4s2` (Linux, 1.8 GB)

---

## 2. Blocker 1 — `diskutil` is invoked with `-plist` in an unusable position

**Severity: release-blocking defect in workstream 4. Every `provision`
invocation fails before it can resolve any disk.**

`e87ctl/src/e87ctl/macos.py:48-52`:

```python
def plist(self, *arguments: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["diskutil", *arguments, "-plist"], check=True, capture_output=True
        )
```

`diskutil` accepts `-plist` only after the verb and before the operand. Measured
on macOS 26.6:

```
diskutil info -plist /             -> OK
diskutil info / -plist             -> FAIL (usage error, rc 1)
diskutil info -plist disk0         -> OK
diskutil info disk0 -plist         -> FAIL
diskutil list -plist               -> OK
diskutil list -plist disk0         -> OK
diskutil list disk0 -plist         -> FAIL
diskutil apfs list -plist          -> OK
diskutil apfs list -plist disk3    -> OK
```

The trailing form therefore works only for the two operand-less calls,
`plist("list")` and `plist("apfs", "list")`. It fails for every operand-carrying
call site:

- `macos.py:229` — `plist("info", "/")` in `_system_physical_stores`
- `macos.py:185` — `plist("info", identifier)` in `_read_whole_disk`
- `macos.py:142,146` — `plist("info", boot_identifier)` in the post-write boot sequence
- `macos.py:313,335` — `plist("list", identifier)`

`_system_physical_stores` is reached first by both `discover_eligible_disks` and
`inspect_target`, so the failure is universal and immediate.

**The correct form is `diskutil <verb…> -plist [operand]`** — the flag after all
verb tokens, before the operand. Note that the verb is two tokens for
`apfs list`, so a naive "insert after argument 0" fix will break that call.

### Observed effect on the specified rejection checks

```
--disk disk3    -> error: diskutil could not inspect disks             exit=1
--disk disk0    -> error: diskutil could not inspect disks             exit=1
--disk disk0s2  -> error: the selected target is a partition, not a whole disk   exit=1
--disk disk4s1  -> error: the selected target is a partition, not a whole disk   exit=1
```

**These exits must not be accepted as gate evidence.** The first two are
vacuous: they are nonzero because `diskutil` never executed successfully, not
because the internal or system-backing guards fired. Only the partition guard
(`macos.py:88`) is genuinely demonstrated, and only because it runs before any
`diskutil` call.

### Why the test suite missed it

All 16 focused macOS tests inject a fake `Diskutil` and assert on parsed
property-list content. Nothing asserts the argument vector actually passed to
`subprocess.run`. A fix should add a test that pins the real argv for at least
one operand-carrying call, otherwise this class of defect recurs silently.

---

## 3. Blocker 2 — the MacBook's SD card reader is not an external disk

**Severity: blocks the gate as written. Needs an orchestrator decision.**

The spare card, inserted in the built-in slot, enumerates as `disk4` and
`diskutil info -plist disk4` reports:

```
BusProtocol        "Secure Digital"
Internal           true
Removable          true
RemovableMedia     true
Ejectable          true
MediaName          "Built In SDXC Reader"
IORegistryEntryName "Apple SDXC Reader Media"
VirtualOrPhysical  "Physical"
WholeDisk          true
TotalSize          127999672320
```

Eligibility is `macos.py:173-174`:

```python
def _eligible(identity: DiskIdentity, protected: set[str]) -> bool:
    return identity.identifier not in protected and not identity.internal
```

and `inspect_target` rejects internal disks outright at `macos.py:91`. macOS
classifies the built-in SDXC reader as internal, so:

- interactive discovery lists **zero** eligible disks, and
- `--disk disk4` is rejected with "the selected disk is internal or backs the
  running system".

The implementation is behaving as specified — "only whole external physical
disks are eligible" — but that rule makes the gate unrunnable on a MacBook Pro's
own card slot. This is a specification/hardware-assumption conflict, not an
implementation bug.

**Decision required.** Two options, and I do not think the validator should pick
unilaterally:

1. **Require a USB SD reader for the gate.** Zero code change; preserves the
   strongest safety invariant in the workstream. Requires updating the gate
   instructions to state the hardware requirement explicitly.
2. **Widen eligibility** to admit internal media that is removable Secure
   Digital, e.g. `internal and Removable and BusProtocol == "Secure Digital"`.
   This weakens the single clearest protection in the design — `disk0` is also
   internal — and would need careful test coverage proving internal non-removable
   disks stay rejected. Higher risk.

Option 1 is the safer default unless there is a product reason to support the
built-in slot.

---

## 4. Blocker 3 — the pinned package snapshot is not applied, so image builds are a coin flip

**Severity: defect in the image builder. Blocks producing the compatible
manifest the gate requires.**

The gate requires "a compatible coordinator image manifest produced by the
provisionable image builder". The only local images predate workstream 6
(`c80a9f6`, 2026-09-09) and their manifests lack `provisioning_interface_version`,
`boot_partition_size_bytes` and `root_filesystem_size_bytes`. `ImageManifest`
forbids extras and requires all three, so `compatible_image_manifests` returns
an empty list for them. A fresh build is mandatory.

Two build attempts at the candidate commit both failed during Debian bootstrap:

```
attempt 1 (20:38)  .../debian-security/20260911T203812Z trixie-security Release [41.8 kB]
                   Ign: .../trixie-security Release.gpg
                   E: The repository '...trixie-security Release' is not signed.
attempt 2 (20:47)  Err: .../debian-security/20260911T204739Z trixie-security Release  404
                   E: The repository '...' does not have a Release file.
both:              E: mmdebstrap failed to run
                   bdebstrap ERROR: mmdebstrap failed with exit code 25
```

**Each attempt requested a snapshot timestamp equal to its own launch time**
(20:38:12 and 20:47:39), not the pinned epoch. `e87ctl/scripts/build-pi-image:6`
declares `PACKAGE_SNAPSHOT_EPOCH=1786579200` (2026-08-13T00:00:00Z) and passes it
to `docker run` as `SOURCE_DATE_EPOCH`. Upstream
`rpi-image-gen/bin/generators/snapgen` reads exactly that variable and falls back
to `datetime.now(tz=utc)` when unset:

```python
sde = os.environ.get("SOURCE_DATE_EPOCH")
epoch = datetime.fromtimestamp(int(sde), tz=timezone.utc) if sde else datetime.now(tz=timezone.utc)
```

I confirmed the variable **is** present inside the container
(`docker run --env SOURCE_DATE_EPOCH=1786579200 … bash -c 'echo $SOURCE_DATE_EPOCH'`
prints it). It is nonetheless absent by the time the generator substitutes
`${SNAPSHOT_ISO8601}` into `templates/debian/apt/trixie-snapshot.sources`. The
exact point where it is dropped is not yet identified; `lib/common.sh:62` shows
`runenv` supports `-i/--ignore-environment`, which is a plausible but unconfirmed
mechanism.

The pin works when applied. Measured against snapshot.debian.org:

```
debian-security 20260813T000000Z (pinned)   Release:200  InRelease:200
debian          20260813T000000Z (pinned)   InRelease:200
debian-security 20260911T203000Z            Release:200  InRelease:200
debian-security 20260911T203812Z (build 1)  Release:200  InRelease:404   <- fatal: present but unsigned
debian-security 20260911T204739Z (build 2)  Release:404  InRelease:404   <- fatal: absent
debian-security <now>                       Release:404  InRelease:404
debian          <now>                       InRelease:200
```

The `trixie-security` suite entered a transition in snapshot.debian.org's view
between 20:30 and 20:38 tonight and is still unavailable at recent timestamps;
`debian` main was healthy throughout. Attempt 1 caught the one partial state apt
treats as fatal. That much was bad luck — but the build should never have been
exposed to it. The 2026-08-13 pin exists precisely to make this reproducible,
and it is intact and signed right now.

This also explains why the 2026-09-09 build succeeded: that instant happened to
be complete. Nothing about the candidate commit changed the outcome.

**Recommended fix:** make `SOURCE_DATE_EPOCH` reach `snapgen`, and fail the build
loudly if the generated sources do not carry the pinned timestamp, rather than
silently falling back to live time. `rpi-image-gen.origin` records the snapshot
origin and the epoch, so the check is cheap.

I deliberately did **not** patch this locally. Doing so would mean the image no
longer derives from `3bac67b`, which would undermine the artifact-to-candidate
binding the gate record depends on.

---

## 5. Specification ambiguity found while following the instructions

The instructions say to set `E87_SYSTEM_STORE` to "the root volume's physical
store". On this machine that resolves to `disk0s2`, which is a **partition**.
Passing it therefore exercises the partition guard, not the system-backing
guard, and duplicates the `E87_SPARE_PARTITION` check. The system-backing guard
can only be exercised with a whole-disk identifier — here `disk3` (the
synthesized container backing root) or `disk0`.

Suggest the instructions name the values explicitly: `E87_SYSTEM_STORE` as the
whole disk or synthesized container backing root, and keep `E87_INTERNAL_DISK`
for a distinct internal whole disk. On a single-internal-disk Mac those two
collapse onto `disk0`/`disk3`, which is worth acknowledging in the record.

---

## 6. Evidence NOT obtained

Everything downstream of disk resolution is untested, because blockers 1 and 2
prevent reaching it:

- resolved spare-card identity and confirmation binding
- identity recheck before writing
- raw-device write via `/dev/rdiskN`
- image-sized SHA-256 readback
- `bootfs` boot-only mount, ZIP injection and readback
- final whole-disk unmount
- secret-free final output and `First boot: pending`

No claim is made about any of these. The card was not written to.

---

## 7. Resume conditions

The gate can be re-attempted when all of the following hold:

1. The `-plist` argument ordering is fixed for all six operand-carrying call
   sites, with a test pinning the real argv.
2. The SD-reader eligibility question is decided — either the gate instructions
   require a USB reader, or eligibility is deliberately widened with tests
   proving internal non-removable disks remain rejected.
3. A coordinator image and manifest are built from the new candidate and
   validate against `ImageManifest`, ideally with the snapshot pin actually
   applied so the build is reproducible rather than time-dependent.
4. The gate instructions disambiguate `E87_SYSTEM_STORE` as described above.

The validation host, recovery package and captured topology are in place and can
be reused immediately for the next attempt.
