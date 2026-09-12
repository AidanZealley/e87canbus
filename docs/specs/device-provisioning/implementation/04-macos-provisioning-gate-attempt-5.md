# Workstream 4 external validation — attempt 5 report

**Verdict: PASSED.** Candidate 5 completed the full macOS writer gate on the M1 Pro MacBook. The
running-system disk, a partition and the synthesized root container were rejected before mutation.
The eligible built-in-reader SD card was then written, fully read back, injected with the verified
provisioning bundle and left wholly unmounted. Final output correctly reports first boot as pending.

## Environment and topology

| Item | Value |
|---|---|
| Candidate commit | `2e29008c5d271fff3cc21fe9e3544f6ecead90b9` (verified with `git rev-parse HEAD`) |
| Working tree | clean, detached HEAD before the attempt |
| Host | MacBook Pro, Apple M1 Pro |
| `sw_vers` | macOS **26.6**, BuildVersion **25G70** |
| Dependency setup | `uv sync --locked` passed |

Structured property lists resolved root snapshot `disk3s1s1` through synthesized container `disk3`
and physical-store partition `disk0s2` to protected whole disk `disk0`. The spare card was whole
disk `disk4`, with partition `disk4s1`. There is no separate internal, non-system whole disk.

`diskutil info -plist disk4` recorded the approved built-in-reader identity: `WholeDisk=true`,
`VirtualOrPhysical=Physical`, `Internal=true`, `BusProtocol=Secure Digital`, `Removable=true`,
`RemovableMedia=true`, `Ejectable=true`, model `Built In SDXC Reader`, and total size
`127999672320` bytes.

## Image and rejection checks

The candidate built this compatible coordinator image:

```text
Manifest: artifacts/images/coordinator/e87-coordinator_2026-09-12_0717Z_2e29008.json
Image SHA-256: f0d4137140577bd12aed168a164c2e580cf03fdcae14e278f4ce61410905e3b5
```

Each required unsafe selector exited 1 before application build or disk mutation:

```text
disk0    error: the selected target is not a physical disk
disk4s1  error: the selected target is a partition, not a whole disk
disk3    error: the selected target is not a physical disk
```

Discovery resolved only `/dev/disk4: Built In SDXC Reader, 127999672320 bytes, serial not reported,
Secure Digital`. The selected profile was `bench`, bound by exact confirmation
`disk4 Built In SDXC Reader 127999672320`.

## Successful write and verification

The corrected production frontend passed `tsc -b` and Vite. The writer then reported:

```text
Unmount of all volumes on disk4 was successful
1538+0 records in
1538+0 records out
6450839552 bytes transferred in 266.748951 secs (24183186 bytes/sec)
6152+0 records in
6152+0 records out
6450839552 bytes transferred in 74.825634 secs (86211626 bytes/sec)
Unmount of all volumes on disk4 was successful
```

The second transfer is the exact image-sized `/dev/rdisk4` readback. The command continued only
after its SHA-256 matched the image manifest, then found the exact `BOOT` volume, mounted only that
partition, copied and read back `e87canbus-provisioning-v1.zip`, and finally unmounted the whole
disk. A zero exit proves both bundle size/digest verification and boot-only mount enforcement.

Secret-free final output:

```text
Prepared coordinator e87-coordinator-67ef0009207f
Target: /dev/disk4: Built In SDXC Reader, 127999672320 bytes, serial not reported, Secure Digital, mounts /Volumes/BOOT
Device ID: 67ef0009-207f-4d13-aacf-fee9a66ff426
Installation ID: rfn2pld32n2lmlia4o7k2qa4bhjfj3ipiqpiio6ksxnnblbdyelq
Image SHA-256: f0d4137140577bd12aed168a164c2e580cf03fdcae14e278f4ce61410905e3b5
Application SHA-256: 7ebe4fb344ad89f2cde8c7b973a6e0f9f2acaa7e7a570c3507d0c926386e3cfc
Provisioning SHA-256: 68c2d307b36a280d1fbab6fafe3021f36c72f4bb22aae2c7130024783068707f
First boot: pending
```

Final `diskutil info disk4` reports no mounted filesystem. Structured final layout contains the
2,147,483,648-byte FAT `BOOT` partition and 4,294,967,296-byte Linux partition with no mount points.

## Conclusion

Every required macOS writer-safety and successful-preparation criterion is evidenced on exact
candidate `2e29008c5d271fff3cc21fe9e3544f6ecead90b9`. The gate is passed. Online first-boot and
two-device behavior remain correctly deferred to workstream 7.
