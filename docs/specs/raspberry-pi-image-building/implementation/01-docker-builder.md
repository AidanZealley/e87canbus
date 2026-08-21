# Workstream 1: Docker builder and base-image proof

Status: accepted.

## Task packet

### Outcome

The repository can build an otherwise unmodified arm64 Raspberry Pi OS Lite Trixie image through
Docker and write a digest-backed artifact below `artifacts/images/coordinator/`. Aidan has built,
flashed and booted that checkpoint on the stated hardware.

### Scope

- Pin `rpi-image-gen`, the arm64 Debian container and package sources.
- Add the Dockerfile and `./scripts/build-pi-image` wrapper.
- Implement host checks, privilege setup, read-only source mounting, writable work/cache/output
  locations, useful failures and cleanup of temporary state.
- Generate the required artifact manifest and verify its SHA-256 digest.
- Ignore all generated images, work directories and caches.
- Add focused tests that do not require Docker.
- Produce exact checkpoint instructions for the M1 Pro.

### Non-goals

Do not add common machine setup, role packages, SD-card writing, Python CLI integration, x86
emulation, Pi 5 support or external artifact storage.

### Initial ownership

- `images/builder/**`
- `scripts/build-pi-image`
- `.gitignore`
- `hosts/tests/test_pi_image_build.py`
- This workstream record

### Required seams

The wrapper must leave room for the common and role definitions without adding a plugin system.
The two final public role names are fixed. A temporary base checkpoint may use the coordinator path,
but no third public build mode may survive this workstream.

### Acceptance criteria

- Static tests cover argument rejection, Docker and architecture checks, artifact placement,
  manifest fields, digest verification and ignored local outputs.
- The wrapper uses a pinned arm64 container and does not require host Python dependencies.
- Source mounts are read-only and writable mounts are limited to explicit build state.
- The checkpoint commit includes no generated image.
- Aidan records a successful Mac build, Imager flash and Pi 4 boot before acceptance.

### Targeted verification

```bash
bash -n scripts/build-pi-image
uv run pytest hosts/tests/test_pi_image_build.py
uv run ruff check hosts/tests/test_pi_image_build.py
```

On the M1 Pro checkpoint:

```bash
./scripts/build-pi-image coordinator
```

## Implementation handoff

- Base commit: `fa9d2fe` (`Record Pi image workflow start`).
- Outcome: Added the shared arm64 Docker builder, the two-role shell entry point, a temporary
  upstream-only Pi 4 base definition, digest-backed manifests and ignored local build state.
  Until the real role definitions land, only the coordinator command may use the base checkpoint;
  a missing console definition fails without producing build state. Each build receives a fresh
  Docker-managed work volume while preserving downloaded packages in a named Docker volume.
- Files changed: `.gitignore`, `images/builder/Dockerfile`, `images/builder/base.yaml`,
  `images/builder/debian.sources`, `scripts/build-pi-image`,
  `hosts/tests/test_pi_image_build.py` and this workstream record. The decision log in `plan.md`
  records the delegated pins.
- Pins and privilege model: `rpi-image-gen` v2.8.0 commit
  `262d4df5a9f9d4133370465399a7958a7c22cdc7`; arm64 `debian:trixie-slim` manifest
  `sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0`;
  Debian and Debian Security snapshots at `20260813T000000Z`; Raspberry Pi archive restricted to
  its upstream `trixie`/`main` source. The two Snapshot sources use HTTP so the slim base can
  install `ca-certificates`; both retain their Debian archive `Signed-By` keyring and APT Release
  metadata verification. The root container receives `CAP_SYS_ADMIN`, which upstream requires for
  mount namespaces. Repository source is read-only. Docker supplies ephemeral Linux volumes for
  `/work` and `/tmp`, a persistent named volume for `/cache` and a host bind for `/output`. This
  keeps target filesystem construction and image assembly off incompatible Docker Desktop mounts.
- Verification: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (17 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py`, `git diff --check`, YAML parsing and confirmation that every
  configured layer exists at the pinned revision. `uv` and Docker are unavailable in this
  environment, so the exact `uv run` commands and a real container build remain pending.
- MacBook, Imager and Pi checkpoint: Candidate `a767497` failed on the M1 Pro during the builder
  image's first `apt-get update`, before `rpi-image-gen` ran or an image artifact existed. The slim
  base could not verify the HTTPS Snapshot certificates before installing `ca-certificates`, so
  APT reported no installation candidate for `ca-certificates` and could not locate Git. Imager
  and Pi boot checks did not run. Candidate `bc0eed2` cleared that failure and reached target
  filesystem construction, then the macOS-backed `/work` bind returned an I/O error while `dpkg`
  installed `libpam-runtime`. The next candidate moves work and package-cache I/O into
  Docker-managed Linux volumes. Candidate `30a068a` completed rootfs construction and the SBOM,
  then `genimage` could not preserve rootfs metadata while copying it into the `/tmp` tmpfs. The
  next candidate also gives image assembly a disposable Docker volume. Imager and Pi boot checks
  remain pending.
- Known limitations: The Raspberry Pi Trixie archive is URL, suite and component pinned but remains
  rolling because Raspberry Pi does not publish an immutable snapshot endpoint. The image digest
  identifies the exact result. The checkpoint contains no test login credentials; supply temporary
  access through Raspberry Pi Imager if boot inspection needs it.
- Specification drift: None. The specification explicitly delegates exact pins, and it requires
  hardware evidence rather than treating remote checks as proof.

## Independent review

- Reviewer: Codex (`gpt-5.6-sol`), fresh workstream reviewer.
- Verdict: Changes requested. The upstream configuration and restricted container invocation are
  credible, but artifact publication can leave an incomplete final result and the focused tests do
  not cover two acceptance-critical failure paths.
- Required findings:
  1. `scripts/build-pi-image:181-182` publishes the image and manifest with two independent `mv`
     calls, while the exit trap cleans only the staging directory. A failed second move or an
     interruption between the calls leaves a final `.img` with no manifest. This breaks the
     digest-backed artifact contract and makes a failed build look partly successful. Keep the
     pair staged until it is complete and make failure cleanup remove any partially published
     pair. Add a focused failure test that proves the artifact directory contains neither final
     file when publication fails.
  2. `hosts/tests/test_pi_image_build.py:34-64` covers a missing Docker executable and a non-arm64
     host, but no test exercises the Docker-daemon failure at `scripts/build-pi-image:102` or the
     container-architecture rejection at `scripts/build-pi-image:132-134`. The latter is the only
     check that proves Docker actually produced an arm64 builder, and both paths are named by the
     static-test acceptance criterion. Add focused behavioral coverage using the existing fake
     Docker approach.
- Optional observations:
  - Several assertions at `hosts/tests/test_pi_image_build.py:134-186` inspect shell source text.
    The tests pass, but argument-capturing fake Docker checks would protect mount, capability and
    invocation behavior with less coupling to formatting when those tests next need revision.
- Questions for orchestrator: None.
- Evidence: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (10 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py`, `git diff --check` and `git check-ignore` passed. Review of
  pinned upstream commit `262d4df5a9f9d4133370465399a7958a7c22cdc7` confirmed all ten configured
  layer names, the `build -S ... -B ... -c ... -- key=value` interface, deploy and apt-cache
  variables, root execution without Podman user namespaces and upstream's stated `CAP_SYS_ADMIN`
  requirement. Docker was unavailable here, so the checkpoint build remains pending. The wrapper
  uses no feature newer than macOS Bash 3.2.

## Resolution

- Original review dispositions: Accepted both required findings. The exit cleanup now removes both final
  names until publication completes, including failed first or second moves and handled
  interruptions. Focused tests cover both move failures, a `TERM` between moves, Docker daemon
  failure and rejection of an x86_64 builder container. The source-string brittleness observation
  remains optional and did not expand this workstream.
- External pre-checkpoint review dispositions: Corrections start from candidate `d8ca86c`. Accepted
  both required findings from Aidan's adversarial review. Missing role definitions now fail, with
  one explicit exception for the coordinator base-image checkpoint. A build removes only
  `.cache/pi-image-build/work/<validated-role>` before recreating it and leaves the package cache
  intact. Focused tests cover both behaviors.
- External optional triage: Accepted the adjacent digest and Git-context simplifications because
  they remove repeated work before and after a long build. The script hashes the image once and
  reuses that digest for the manifest and output. It resolves the commit and dirty state once
  before building and reuses the commit in the build ID and manifest. Deferred the remaining
  optional observations, including the function parameters, file-size helper, argument handling,
  repeated config-relative path, snapshot comment, output glob and broader source-assertion test
  changes.
- MacBook checkpoint attempt 1 disposition: Accepted the focused bootstrap correction. Both dated
  Debian Snapshot URIs now use Snapshot's supported HTTP transport so the pinned slim base can
  install `ca-certificates`. The sources retain `Signed-By` and `Check-Valid-Until`, and the focused
  static check rejects a `Trusted: yes` bypass. No pin, base image, package, privilege or wrapper
  behavior changed.
- MacBook checkpoint attempt 2 disposition: Candidate `bc0eed2` proved the certificate correction,
  then failed when `dpkg` received `EIO` while trying to stat a PAM manual page in the target root.
  Moved `/work` from the macOS bind mount to an anonymous Docker volume removed by `--rm`. The
  persistent package cache now uses the named `e87canbus-pi-image-packages` volume. `/output`
  remains a host bind so the completed artifact reaches the Mac.
- MacBook checkpoint attempt 3 disposition: Candidate `30a068a` completed rootfs construction and
  SBOM generation, then `genimage` failed when `cp -a` could not preserve metadata for
  `var/log/journal` in its `/tmp` staging tree. Pinned upstream uses that tree to copy the complete
  rootfs before assembling the image. Replaced the tmpfs with a second anonymous Docker volume;
  `--rm` removes both disposable volumes when the build container exits.
- Simplification/deletion pass: Publication still uses the existing staging directory, one success
  bit and one cleanup function. Role selection has one narrow checkpoint exception rather than a
  fallback mode. Docker removes the anonymous work volume with the container, so the wrapper needs
  no work reset or cleanup policy. The bootstrap fix changes only the two source URIs and needs no
  Dockerfile workaround or temporary trust configuration. Docker now owns the high-I/O build
  locations. The legacy `.cache` ignore remains so state from earlier checkpoint attempts does not
  dirty existing checkouts, but the wrapper no longer creates or uses that tree.
- Final verification: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (17 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py` and `git diff --check` pass. Aidan's M1 Pro produced and
  Raspberry Pi Imager wrote the accepted artifact; the Pi 4 booted it to a login prompt.

## Closure review

- Verdict: Software closure accepted. The workstream is ready for its checkpoint candidate and
  remains subject to the documented MacBook, Imager and Raspberry Pi 4 result.
- Remaining required findings: None. Cleanup owns both final artifact names until both moves
  finish, and it removes either partial file on move failure or a handled `HUP`, `INT` or `TERM`.
  Focused tests cover failed first and second publication moves, termination between moves, an
  unavailable Docker daemon and rejection of an x86_64 builder container. Remediation introduced
  no release-blocking defect.
- Evidence: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (15 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py` and `git diff --check` passed during closure review.
- Accepted commit: `7f78f3f` (`Keep Pi image assembly on Docker storage`).
- Pre-checkpoint correction closure: Accepted. No required finding remains from Aidan's
  adversarial review, and the corrections introduced no release-blocking regression. A missing
  console definition exits before Docker, artifact directories or role cleanup; only coordinator
  has the explicit base-checkpoint exception. The validated coordinator work directory resets on
  each build while the package cache remains intact. The image is hashed once, and that digest is
  reused in the manifest and command output. One pre-build commit read and one dirty-state read
  supply the build ID and manifest.
- Pre-checkpoint closure evidence: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (17 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py` and `git diff --check` passed. Focused temporary probes also
  proved that missing-role failure does not invoke Docker or alter existing work state, work reset
  does not follow a role-directory symlink, the package cache survives, the digest helper runs
  once, and the manifest commit and build-ID suffix come from the same single commit lookup. Static
  inspection found no shell feature newer than macOS Bash 3.2. `uv` and Docker are unavailable in
  this environment.
- MacBook checkpoint attempt 1: Failed at candidate `a767497`. Docker resolved the pinned arm64
  Debian base, then both pinned HTTPS Snapshot sources failed certificate verification during
  `apt-get update`. The subsequent `apt-get install` found neither `ca-certificates` nor Git and
  exited 100. No artifact was produced, so Imager and Pi checks remain pending. The accepted
  correction is to use Snapshot's supported HTTP transport for the bootstrap while retaining
  `Signed-By` and APT's Release-file verification.
- MacBook checkpoint attempt 1 correction closure: Accepted. Both dated Snapshot `InRelease`
  files were fetched over HTTP and contained signed Release metadata. The sources still select the
  Debian archive keyring with `Signed-By`; no trusted, insecure or TLS-verification bypass was
  added. The builder revision, base digest, snapshot dates, package list and build behavior are
  unchanged. `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (17 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py` and `git diff --check` passed. Docker is unavailable in this
  environment, so the replacement MacBook checkpoint remains the required runtime proof.
- MacBook checkpoint attempt 2: Candidate `bc0eed2` reached `mmdebstrap`. `libpam-runtime`
  unpacked, then `dpkg` failed to stat `usr/share/man/man7/PAM.7.gz` with `EIO` inside the
  macOS-backed `/work` bind. Dependency messages around `util-linux` were expected forced-unpack
  warnings, not the failure. The next candidate uses Docker-managed Linux volumes for work and
  package cache; only source and finished artifacts cross the Docker Desktop file-sharing boundary.
- MacBook checkpoint attempt 3: Candidate `30a068a` completed `mmdebstrap`, all layer hooks and
  SBOM generation. During image assembly, pinned upstream passed a directory below `/tmp` as
  `genimage --tmppath`; `genimage` then failed because `cp -a` could not preserve metadata for
  `var/log/journal` on the tmpfs. The next candidate uses an anonymous Docker volume for `/tmp`,
  keeping image assembly on Docker-managed Linux storage with automatic removal on container exit.
- MacBook checkpoint attempt 4: Passed at candidate `7f78f3f`. The M1 Pro built
  `20260821T213003Z-7f78f3fc2f8e.img` (1,837,105,152 bytes) with SHA-256
  `fd765de34be4382f5ce79bdae7ea3cf1a7a9a20db45ed690f5ef9df98d850181`.
  Raspberry Pi Imager wrote the image successfully. Aidan's photograph shows the Raspberry Pi 4
  reaching Debian GNU/Linux 13 on `tty1`, starting SSH, reaching `multi-user.target` and presenting
  the `pi4-aubzwc` login prompt with no failed units visible. Workstream 1 is accepted.
