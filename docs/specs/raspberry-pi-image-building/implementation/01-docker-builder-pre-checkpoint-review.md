# Workstream 1 pre-checkpoint review

Reviewed commit: `d8ca86c` (`Add Raspberry Pi image builder`).
Reviewer: Claude Opus 5, at Aidan's request, before the M1 Pro checkpoint build.
Status: findings for the workstream 1 implementation agent.

This is an extra pass over the checkpoint candidate, not a replacement for the recorded
independent or closure reviews. Record dispositions in the `Resolution` section of
[01-docker-builder.md](01-docker-builder.md) using the normal accept or reject with reason format.

## What already holds up

The pins are real: a git SHA for `rpi-image-gen`, a manifest digest for the arm64 base container,
and dated Debian snapshots. The container gets `CAP_SYS_ADMIN` rather than `--privileged`, source
mounts read-only, and writable mounts are limited to `/work`, `/cache`, `/output` and the `/tmp`
tmpfs. Staging then publishing under one cleanup function does what the earlier review asked, and
the failure tests around it are worth keeping. All eleven manifest fields required by the plan are
present and correctly typed, including a real JSON `null` for `git_commit` when there is no HEAD.
`.gitignore` covers both generated trees.

Verification reproduced here: `bash -n scripts/build-pi-image` is clean and
`hosts/tests/test_pi_image_build.py` passes with 15 tests.

## Required findings

### 1. `console` silently builds and mislabels the base image

`scripts/build-pi-image:108-113` falls back to `images/builder/base.yaml` whenever
`images/<role>/image.yaml` does not exist. Today `./scripts/build-pi-image console` produces an
artifact whose manifest claims `"role": "console"` while containing the unmodified base image.

The plan's cross-workstream contract makes the manifest the record of the role, and the
specification has the later provisioning CLI use that manifest to reject an incompatible image. A
mislabeled artifact defeats the one output that matters at this stage.

The fallback also does not remove itself. Once workstreams 3 and 4 add role configs, a wrong or
missing path silently yields a base image under a role name instead of an error.

Make a missing role config a hard failure. Handle the checkpoint case explicitly, either by
accepting only `coordinator` until workstream 2 lands or by failing `console` with a message that
names the workstream that will implement it. Do not keep a general silent fallback.

### 2. The work directory is never reset and cleanup does not own it

`.cache/pi-image-build/work/<role>` persists across runs, and the exit trap at
`scripts/build-pi-image:127-133` touches only the staging directory and the published pair. A
build that dies partway through leaves state behind, and the next run starts on top of it.

The task packet puts "cleanup of temporary state" in scope. Either clear `WORK_DIR` at the start of
a build or document the exact command to clear it in the checkpoint instructions. Keep
`.cache/pi-image-build/packages` intact either way so a retry stays cheap, which matters more than
usual given the download risk noted below.

## Optional observations

These are worth doing while the file is open. None of them blocks the checkpoint.

### Hash the image once

`write_manifest` computes the digest, then the check at `scripts/build-pi-image:82-85` reads that
digest back out of the file it just wrote and rehashes the same image to compare. Line 195 hashes a
third time for the final message. On a multi-gigabyte image that is real wall-clock time for a
check that cannot meaningfully fail. Compute the digest once and reuse it.

### Collect the git context in one place

`scripts/build-pi-image:116` runs `git rev-parse --short=12 HEAD` for the build ID, then lines
178-187 run `rev-parse` and `status` again during publication. Resolve the full commit once near the
top, derive the short form with `${GIT_COMMIT:0:12}`, and read the dirty flag alongside it. That is
one git invocation instead of two, roughly ten lines down to four, and the build ID can no longer
disagree with the manifest about which commit produced the image. It also moves the git block out of
the middle of the publish sequence, which currently reads stage image, resolve git, write manifest,
move, move.

### Drop `write_manifest`'s parameters

The function takes six positional arguments and spends eight lines unpacking them into locals.
Every one of those values is already a global in scope, and the function has exactly one caller.
Make it zero-argument and read the globals, or inline the heredoc at the call site. With the
redundant digest check removed, it goes from about 35 lines to 15.

### Replace `file_size` with `wc -c`

The `stat -f %z` and `stat -c %s` probe at `scripts/build-pi-image:42-50` is nine lines of BSD
versus GNU handling. `size=$(( $(wc -c < "${image}") ))` is portable and the arithmetic expansion
strips BSD `wc`'s leading whitespace, which matters because the value goes into JSON as a number.
Both implementations use `fstat` for `-c` on a regular file, so it does not read the image.

### Use one exit path for bad arguments

`scripts/build-pi-image:88-99` runs the arity check and the role check as separate blocks that each
call `usage` and exit 2. One case statement covers both and gives `usage` a single caller:

```bash
case "$#:${1:-}" in
    1:coordinator | 1:console) ;;
    *) usage; exit 2 ;;
esac
```

### Small repetitions

`${CONFIG_PATH#"${REPO_ROOT}/"}` is expanded at both line 147 and line 148. Assign it once.

`PACKAGE_SNAPSHOT_EPOCH="1786579200"` is 2026-08-13T00:00:00Z and has to stay in sync with the two
dated URLs in `images/builder/debian.sources`. The date appears three times in the repository and
only two of them are readable. A trailing comment stops a later snapshot bump from leaving the
epoch behind.

### After the checkpoint, the output glob can go

Lines 169-176 glob for `*.img` and assert exactly one match because the deploy filename that
`rpi-image-gen` produces is not yet known. That is the right call while it is unknown. Once the real
name is observed on the Mac, this becomes a direct path and both the array and the count check
disappear.

### Trim the tests that assert on shell source text

`test_builder_and_package_sources_are_immutable_where_upstream_allows`
(`hosts/tests/test_pi_image_build.py:247`) restates the pins as string literals. It cannot fail
unless someone changes a pin, at which point it fails by design and the pin gets edited in two
places. It protects no behavior and should go. The earlier reviewer's observation about
source-string assertions applies more broadly to the mount and manifest-field tests at lines 264-300,
which pass whether or not the script works. Convert them to argument-capturing fake Docker checks or
drop them when those tests next need revision. The behavioral tests covering publication failure,
interruption, daemon failure and container architecture are the valuable ones and should stay.

## Do not do

Do not wrap the main body in `main()` with phase functions. The linear script already reads as
validate, resolve, build, run, publish, and bash functions plus `readonly` globals fight each other.
Grouping the path computation and separating the phases with blank lines gets the same readability
without the ceremony.

Do not add flags, aliases or a compatibility path to preserve the role fallback in finding 1.

## Checkpoint risks for Aidan, not implementation work

These are things to check on the MacBook. They are not defects in the current diff, but a failure
during the checkpoint will most likely be one of them rather than a bug in the wrapper.

Raspberry Pi Imager has two customization mechanisms. The newer one writes `custom.toml` to the boot
partition and only does something if the image contains `raspberrypi-sys-mods` and its firstboot
units. The older one writes `firstrun.sh` and appends `systemd.run=` to `cmdline.txt`, which needs
only systemd and a shell. If Imager writes `custom.toml` and nothing in the image consumes it, the
Pi boots with no user and no way in. The current layer list includes `openssh-server` but creates no
user, no password and no `authorized_keys`, so the whole checkpoint login path depends on this. It
can be checked before building:

```bash
docker build --platform linux/arm64 -f images/builder/Dockerfile -t pi-image-builder-probe images/builder
docker run --rm --platform linux/arm64 --entrypoint sh pi-image-builder-probe \
  -c 'grep -rn "raspberrypi-sys-mods\|userconf" /opt/rpi-image-gen/layer | head -20'
```

If nothing matches, add the layer that provides it before building, or agree that HDMI plus a
keyboard reaching a login prompt is the pass criterion for checkpoint one.

Imager may not offer customization for a custom `.img` at all. The settings control has historically
been disabled when selecting a local file rather than a catalogue image. Confirm the installed
version offers it before spending an hour on a build.

Wi-Fi customization will not work whichever mechanism fires. The layers use `systemd-net-min` and
`iwd`, while Imager writes either a NetworkManager profile or `wpa_supplicant.conf`, and neither
package is in the image. Ethernet is fine for checkpoint one, but a Wi-Fi failure should not be read
as a build problem.

`snapshot.debian.org` is slow and rate-limits, and a full base pull from it often returns 503s. If
the build dies during package fetch, suspect that before the wrapper.

`--tmpfs /tmp:exec` sets no size and Docker Desktop's default RAM and disk allocations are modest.
A "no space left on device" failure mid-build means Docker Desktop resources, not the script.

## Verification after changes

```bash
bash -n scripts/build-pi-image
uv run pytest hosts/tests/test_pi_image_build.py
uv run ruff check hosts/tests/test_pi_image_build.py
```

Finding 1 needs a focused test proving that a role without an image definition fails instead of
producing an artifact. Finding 2 needs no new test if the reset is documented rather than
implemented.
