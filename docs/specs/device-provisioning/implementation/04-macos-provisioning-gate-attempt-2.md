# Workstream 4 external validation — attempt 2 report

**Verdict: FAILED, but two of the three attempt 1 blockers are fixed and verified on real
hardware.** One blocker remains, and it is a newly exposed defect that the previous bug was
masking. No destructive operation was attempted; the SD card was not written to.

---

## 1. Environment

| Item | Value |
|---|---|
| Candidate commit | `d0a22c191e8402602f299ec2b77006c9a59e400d` (verified with `git rev-parse HEAD`) |
| Working tree | clean, detached HEAD |
| Host | MacBook Pro, Apple M1 Pro |
| `sw_vers` | macOS **26.6**, BuildVersion **25G70** |
| uv | 0.11.11, `uv sync --locked` clean |
| Docker | Docker Desktop 20.10.14, native aarch64 |

### Targeted verification at the candidate (all passed)

```
uv run pytest e87ctl/tests -q   -> 117 passed   (was 104 at attempt 1)
uv run ruff check e87ctl        -> All checks passed
uv run mypy                     -> Success: no issues found in 143 source files
```

### Recorded topology

- Root volume `disk3s1s1`; synthesized container backing it `disk3`
- Root physical-store partition `disk0s2`; whole physical disk containing it `disk0`
- Spare card whole disk `disk4`; partition on that card `disk4s1`

Environment values used: `E87_SYSTEM_DISK=disk0`, `E87_ROOT_CONTAINER=disk3`,
`E87_SPARE_DISK=disk4`, `E87_SPARE_PARTITION=disk4s1`.

**There is no separate internal, non-system whole disk on this machine.** As the instructions
direct, that fact is recorded here rather than substituting a partition for the check.

### Spare card identity (`diskutil info -plist disk4`)

```
WholeDisk          true
VirtualOrPhysical  "Physical"
Internal           true
BusProtocol        "Secure Digital"
Removable          true
RemovableMedia     true
Ejectable          true
MediaName          "Built In SDXC Reader"
TotalSize          127999672320
```

All five conditions of the approved built-in-reader case are satisfied.

---

## 2. Blocker 1 — `diskutil` argument order: FIXED and verified

`SystemDiskutil.plist` now places `-plist` after the verb tokens and before the operand, with the
two-token `apfs list` verb handled explicitly. Verified against real `diskutil` on macOS 26.6:
discovery, whole-disk inspection and APFS enumeration all succeed.

The fix also corrected a second latent defect that attempt 1 did not reach: `_read_whole_disk`
checked `info.get("Whole")`, but real `diskutil` emits **`WholeDisk`**. I confirmed there is no
`Whole` key in live output. With only the argument-order fix, every real disk would still have
been rejected as "not a whole disk". Good catch.

### Live discovery result

```
ELIGIBLE DISKS:
  /dev/disk4: Built In SDXC Reader, 127999672320 bytes, serial not reported,
              Secure Digital, built-in removable media, mounts /Volumes/BOOT

  disk0    REJECTED -> the selected target is not a physical disk
  disk3    REJECTED -> the selected target is not a physical disk
  disk4    ACCEPTED
  disk4s1  REJECTED -> the selected target is a partition, not a whole disk
  disk0s2  REJECTED -> the selected target is a partition, not a whole disk
```

Confirmation string bound to the resolved identity:
`disk4 Built In SDXC Reader 127999672320`

---

## 3. Blocker 2 — built-in SD reader eligibility: FIXED and verified

`_supported_media` admits internal media only when `BusProtocol` is exactly `Secure Digital` and
`Removable`, `RemovableMedia` and `Ejectable` are all true. The card is accepted; the internal SSD
and the synthesized container are not. Discovery lists exactly one eligible disk.

### Specified rejection checks (card untouched afterwards)

```
E87_SYSTEM_DISK     (disk0)    exit=1  error: the selected target is not a physical disk
E87_SPARE_PARTITION (disk4s1)  exit=1  error: the selected target is a partition, not a whole disk
E87_ROOT_CONTAINER  (disk3)    exit=1  error: the selected target is not a physical disk
```

`diskutil list disk4` after the checks shows the original FDisk scheme, `BOOT` and Linux partitions
unchanged.

---

## 4. Observation — the system-backing guard is shadowed on Apple Silicon

Not a blocker, but it affects how the evidence should be read.

On this hardware the internal SSD reports:

```
disk0   VirtualOrPhysical "Unknown"   BusProtocol "Apple Fabric"   MediaName "APPLE SSD AP0512R"
disk3   VirtualOrPhysical "Virtual"
disk4   VirtualOrPhysical "Physical"
```

Apple Fabric NVMe reports `Unknown`, not `Physical`. `inspect_target` calls `_read_whole_disk`
first, which rejects on the media-type check before the protected-set comparison runs. So `disk0`
is rejected with "not a physical disk" rather than "backs the running system".

The guard itself is correct and reachable in principle — I confirmed directly that
`_system_physical_stores` resolves the physical store `disk0s2` up to its whole disk and returns
`{'disk0'}`. The acceptance criterion "every system-backing or internal disk is rejected" is
therefore met, with defence in depth: three independent checks each reject `disk0`.

**Suggested, not required:** consider evaluating the protected set before the media-type check so
the reported reason matches the actual protection. Purely a diagnostic-accuracy improvement; the
safety outcome is identical either way. Recording it so the gate evidence is not misread as proof
that the protected-set path executed.

---

## 5. Blocker 3 — snapshot pin: fix works, but exposed a second defect underneath

### The pin fix is confirmed effective

Both repositories now resolve to the pinned epoch, not the build's launch time:

```
archive/debian/20260813T000000Z
archive/debian-security/20260813T000000Z
```

`SOURCE_DATE_EPOCH=1786579200` now appears in the bdebstrap argument list, and
`images/post-build.sh` adds a guard that fails the build if the generated origin does not match.
That is exactly the right shape of fix.

### The build still fails

```
E: Release file for https://snapshot.debian.org/archive/debian-security/20260813T000000Z/
   dists/trixie-security/InRelease is expired (invalid since 23d 1h 5min 50s).
   Updates for this repository will not be applied.
E: apt-get update ... exited with 100
E: mmdebstrap failed to run          bdebstrap ERROR: exit code 25
```

The upstream template `rpi-image-gen/templates/debian/apt/trixie-snapshot.sources` ends each stanza
with:

```
Options: check-valid-until=no
```

`Options:` is one-line `sources.list` syntax. In a deb822 `.sources` file it is an unknown field and
is silently ignored; the correct deb822 field is `Check-Valid-Until: no`. Debian's security archive
signs Release files with a validity window of about a week, so **any pin older than roughly seven
days fails permanently** under the current template.

### Proof

Run inside the pinned builder image against the pinned URL, with only the test source enabled:

```
A) Options: check-valid-until=no   -> E: ... is expired (invalid since 23d 1h 6min 46s)
B) Check-Valid-Until: no           -> clean, no errors
```

### Why this did not appear before

While builds used their own launch time, the Release file was always fresh and the validity check
never triggered. Correcting the pin is what exposed it. The two defects were coupled; fixing the
first was still correct.

### Minimal fix

Either supply a project-owned sources template using `Check-Valid-Until: no`, or pass
`--aptopt 'Acquire::Check-Valid-Until "false"'` through to bdebstrap. This was deliberately not
patched locally, so that the image continues to derive from the candidate commit.

---

## 6. Recommendation — reconsider the historical snapshot pin

Aidan raised this directly during the attempt, and his position is recorded here as the decision
input:

> He is **not concerned about package drift between devices or between full device installs.** If a
> version issue ever appears in the field, reprovisioning every device is an acceptable response.
> He does not want bloated code or blocked progress for what he considers a relatively minor issue.

The findings below support treating the pin as optional rather than load-bearing.

**The pin was never a considered decision in this feature.** `PACKAGE_SNAPSHOT_EPOCH` was introduced
on 2026-08-20 in "Add Raspberry Pi image builder", set to 2026-08-13, and has never been bumped.
Workstream 1 explicitly listed changes to the accepted Docker builder as a non-goal, so nothing
since has re-examined it. It is an inherited convenience value that is now 29 days old.

**The guarantee it pays for is not delivered.** The builder runs with `IGconf_image_disksig=random`,
so images are not byte-identical across builds of the same commit regardless of the pin.
Bit-reproducibility is the strongest argument for a fixed historical snapshot, and this pipeline
cannot provide it.

**The pin has ongoing costs.** It ships a month-old package set onto a device running a WPA3 access
point, nginx TLS/mTLS and SSH, and the gap widens with no process prompting a bump. It also makes
the build structurally fragile, as section 5 shows.

**What the pin genuinely mitigates** is drift between the coordinator and console images when they
are built weeks apart, in the WPA3/PMF, TLS and Chromium certificate paths. Given Aidan's stated
tolerance, this does not justify the machinery, and the residual risk is better handled by building
both role images in one batch from a single snapshot value so the two devices always match each
other.

**Suggested direction, for the orchestrator to accept or reject:**

1. Build both role images in one batch so coordinator and console always agree.
2. Drop the frozen historical epoch. Use the live archive, or a pin bumped deliberately per release.
3. Rely on the already-enabled SBOM (`IGconf_sbom_enable=y`) plus the image manifest for
   traceability, answering "what is on this device?" rather than "can I rebuild this bit for
   bit?".
4. If any pin is retained, `Check-Valid-Until` must be fixed regardless, since that is what blocks
   the build today.

Debian stable moves almost exclusively for security fixes, so unpinned drift mostly delivers
patches rather than churn. Option 2 plus option 1 is both the smaller diff and the safer device.

---

## 7. Evidence NOT obtained

No compatible image manifest exists, so the destructive path could not run. Untested:

- resolved spare-card identity carried through confirmation into the writer
- identity recheck immediately before writing
- raw-device write via `/dev/rdisk4`
- image-sized SHA-256 readback
- `bootfs` boot-only mount, ZIP injection and readback
- final whole-disk unmount
- secret-free final output with three artifact digests and `First boot: pending`

No claim is made about any of these. The card was not written to.

Note the card currently carries a `BOOT` FAT32 partition mounted at `/Volumes/BOOT` and a Linux
partition from prior unrelated use. The writer is expected to unmount the whole disk before writing;
that behavior is untested here.

---

## 8. Resume conditions

1. `Check-Valid-Until` is corrected, or the pin is removed per section 6, so the coordinator image
   and manifest build successfully from the candidate and validate against `ImageManifest`.
2. Optionally, the protected-set check is evaluated before the media-type check so the rejection
   reason for `disk0` reports the actual protection (section 4).

Everything else is in place. The validation host, recovery package
(`~/e87-installation/gate-w4.json`, outside the checkout), captured topology and eligible card are
ready, and the disk-safety half of the gate is now evidenced. The remaining work is a build fix,
then the destructive run.

## 9. Orchestrator disposition

Aidan accepted target-package drift between devices and releases and accepted reprovisioning all
devices if a package-version problem appears. Workstream 1 will use pinned upstream's rolling
Trixie minbase target layer and remove the historical epoch and origin guard. The pinned builder
revision, builder container and its working source configuration remain unchanged.

The correction will not add a build-both command, pin-bump workflow, SBOM changes or an apt-validity
workaround. The suggested system-disk diagnostic reorder is also rejected because all measured
paths already fail safely. The gate remains `Troubleshooting` until a corrected candidate builds a
compatible image and the remaining destructive-path evidence passes.
