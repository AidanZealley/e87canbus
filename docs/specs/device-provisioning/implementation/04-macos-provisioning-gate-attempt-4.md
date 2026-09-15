# Workstream 4 external validation — attempt 4 report

**Verdict: FAILED after a verified raw image write, before provisioning-bundle injection.** The
attempt 3 application-build blocker is fixed. Candidate 4 built the application, wrote the complete
image to the spare card and passed the image-sized SHA-256 readback. It then rejected the written
image because its boot partition is labelled `BOOT`, while the reviewed writer and image contract
require exactly `bootfs`. The whole card was unmounted during cleanup.

## Environment and topology

| Item | Value |
|---|---|
| Candidate commit | `0f29317e2887975b29e218e653314bd83d8a8597` (verified with `git rev-parse HEAD`) |
| Working tree | clean, detached HEAD before the attempt |
| Host | MacBook Pro, Apple M1 Pro |
| `sw_vers` | macOS **26.6**, BuildVersion **25G70** |
| Dependency setup | `uv sync --locked` passed |

Structured property lists again resolved root snapshot `disk3s1s1` through synthesized container
`disk3` and physical-store partition `disk0s2` to protected whole disk `disk0`. The spare card was
whole disk `disk4`, with `disk4s1` used for the partition rejection. There is no separate internal,
non-system whole disk on this machine.

`diskutil info -plist disk4` recorded `WholeDisk=true`, `VirtualOrPhysical=Physical`,
`Internal=true`, `BusProtocol=Secure Digital`, `Removable=true`, `RemovableMedia=true`,
`Ejectable=true`, model `Built In SDXC Reader`, and total size `127999672320` bytes.

## Passed evidence

`uv run e87ctl image build coordinator` produced the compatible candidate image:

```text
Manifest: artifacts/images/coordinator/e87-coordinator_2026-09-12_0635Z_0f29317.json
Image SHA-256: 5dc6a8837b39971d39c90c97f9c6bbef516e8373a2cded3ae83e6dbfba44ddc7
```

All required unsafe-selector commands exited 1 before application build or disk mutation:

```text
disk0    error: the selected target is not a physical disk
disk4s1  error: the selected target is a partition, not a whole disk
disk3    error: the selected target is not a physical disk
```

Interactive and non-interactive discovery resolved only:

```text
/dev/disk4: Built In SDXC Reader, 127999672320 bytes, serial not reported,
            Secure Digital, built-in removable media, mounts /Volumes/BOOT
```

The exact confirmation was `disk4 Built In SDXC Reader 127999672320`, with profile `bench`.
The corrected production frontend ran `tsc -b` and Vite successfully. The writer unmounted all
volumes, wrote the image through `/dev/rdisk4`, then completed the exact image-sized readback. The
code reaches boot-partition discovery only after comparing that readback digest to the manifest, so
the subsequent failure proves the readback matched
`5dc6a8837b39971d39c90c97f9c6bbef516e8373a2cded3ae83e6dbfba44ddc7`.

## Blocking failure

The command then exited nonzero with:

```text
error: written disk does not have exactly one bootfs partition
```

Live `diskutil list -plist disk4` after the write reports:

```text
disk4s1  VolumeName=BOOT  Content=Windows_FAT_32  Size=2147483648
disk4s2                   Content=Linux           Size=4294967296
```

The writer's `_boot_partition` accepts only `VolumeName == "bootfs"`. The image builder actually
created the FAT filesystem with `mkdosfs ... -n 'BOOT'`. This contradicts the workstream 6 handoff
and `images/README.md`, which state that the image preserves the exact `bootfs` label consumed by
the writer. Fixtures model `bootfs`, so automated writer tests did not expose the assembled-image
contract mismatch.

The writer rejected the disk before mounting `disk4s1` or copying
`e87canbus-provisioning-v1.zip`. Its `finally` cleanup unmounted the whole disk; `diskutil info
disk4` confirms it remains unmounted.

## Resume condition

Correct the provisionable image to emit the exact `bootfs` label from the same configuration used
by the assembled image, then record and push a new combined candidate. Re-run the complete gate.
The raw write and readback are now physically evidenced, but boot-only mount, ZIP injection and
readback, successful final output and `First boot: pending` remain untested.
