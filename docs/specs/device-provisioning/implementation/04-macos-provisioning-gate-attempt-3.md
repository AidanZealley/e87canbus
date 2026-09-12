# Workstream 4 external validation — attempt 3 report

**Verdict: FAILED before disk mutation.** Candidate 3 fixes the target-image build blocker from
attempt 2, and all required unsafe disk selectors are rejected on real hardware. The interactive
path then fails while building the application because the frontend build excludes a repository-root
test fixture that TypeScript resolves during the production build. The SD card was not unmounted or
written.

## Environment and topology

| Item | Value |
|---|---|
| Candidate commit | `aa5f0f3280f987ce2ffd669120e677e3f2b8a405` (verified with `git rev-parse HEAD`) |
| Working tree | clean, detached HEAD before the attempt |
| Host | MacBook Pro, Apple M1 Pro |
| `sw_vers` | macOS **26.6**, BuildVersion **25G70** |
| Dependency setup | `uv sync --locked` passed |

Structured `diskutil list -plist`, `diskutil apfs list -plist` and `diskutil info -plist /`
showed the same unambiguous topology as attempt 2:

- root snapshot `disk3s1s1`; synthesized container `disk3`
- root physical-store partition `disk0s2`; containing whole physical disk `disk0`
- spare-card whole disk `disk4`; partition `disk4s1`
- no separate internal, non-system whole disk exists on this machine

`diskutil info -plist disk4` recorded the approved built-in-reader identity: `WholeDisk=true`,
`VirtualOrPhysical=Physical`, `Internal=true`, `BusProtocol=Secure Digital`, `Removable=true`,
`RemovableMedia=true`, `Ejectable=true`, model `Built In SDXC Reader`, and total size
`127999672320` bytes.

## Image build and disk-safety evidence

`uv run e87ctl image build coordinator` completed successfully against the rolling Trixie layer.
It produced:

```text
Manifest: artifacts/images/coordinator/e87-coordinator_2026-09-11_2240Z_aa5f0f3.json
Image SHA-256: 8a52a7c21eb65ebf0e0a84cfa1e4230802bd5b05b7df4ab5ac5d563995cba98d
```

This closes attempt 2's target-image blocker. With that compatible manifest, every specified
rejection command exited nonzero before application build or disk mutation:

```text
disk0    exit=1  error: the selected target is not a physical disk
disk4s1  exit=1  error: the selected target is a partition, not a whole disk
disk3    exit=1  error: the selected target is not a physical disk
```

As in attempt 2, Apple Silicon reports the internal SSD's `VirtualOrPhysical` value as `Unknown`,
so the media-type guard rejects `disk0` before the resolved protected-set guard. The target is
nevertheless safely rejected.

Interactive discovery listed only `disk4`. The selected identity and exact confirmation were:

```text
/dev/disk4: Built In SDXC Reader, 127999672320 bytes, serial not reported,
            Secure Digital, built-in removable media, mounts /Volumes/BOOT
disk4 Built In SDXC Reader 127999672320
```

## Blocking failure

After confirmation, provisioning built the current application. The coordinator frontend failed
during `tsc -b`:

```text
src/components/simulator-workbench/components/neo-trellis-panel/button-pad-renderer.test.ts(3,25):
error TS2307: Cannot find module
'../../../../../../../../protocol/test-vectors/button-pad-program-v2.json'
or its corresponding type declarations.
```

The import is valid in the checkout and resolves to
`protocol/test-vectors/button-pad-program-v2.json`. The application builder, however, copies only
`/source/frontend` into `/work/frontend` before running the workspace production build. The relative
import therefore resolves to `/work/protocol/...`, which is absent. Production TypeScript compilation
includes this test file, exposing the incomplete build input.

The command exited 1 with `error: could not provision the selected disk`. No `diskutil unmountDisk`,
`sudo dd`, readback, boot-volume mount or ZIP copy occurred. Afterwards `disk4s1` retained its
original UUID `BBD0C153-0808-398D-B2CA-D245C508F7EC`, geometry and `/Volumes/BOOT` mount, confirming
the card was not mutated.

## Evidence not obtained and resume condition

Still untested are the raw-device write, image-sized SHA-256 readback, boot-only injection and ZIP
readback, final whole-disk unmount, and secret-free success output with `First boot: pending`.

Resume with a corrected candidate whose application build either supplies the shared protocol test
vector to the frontend build context or excludes test-only sources from production TypeScript
compilation. Re-run the full gate from the exact corrected commit; the destructive path has not yet
been exercised.
