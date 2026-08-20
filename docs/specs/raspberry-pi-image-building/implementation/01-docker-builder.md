# Workstream 1: Docker builder and base-image proof

Status: closure review.

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
- Files changed: `.gitignore`, `images/builder/Dockerfile`, `images/builder/base.yaml`,
  `images/builder/debian.sources`, `scripts/build-pi-image`,
  `hosts/tests/test_pi_image_build.py` and this workstream record. The decision log in `plan.md`
  records the delegated pins.
- Pins and privilege model: `rpi-image-gen` v2.8.0 commit
  `262d4df5a9f9d4133370465399a7958a7c22cdc7`; arm64 `debian:trixie-slim` manifest
  `sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0`;
  Debian and Debian Security snapshots at `20260813T000000Z`; Raspberry Pi archive restricted to
  its upstream `trixie`/`main` source. The root container receives `CAP_SYS_ADMIN`, which upstream
  requires for mount namespaces. Repository source is read-only. Only `/work`, `/cache`, `/output`
  and an executable `/tmp` tmpfs are writable.
- Verification: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (15 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py`, `git diff --check`, YAML parsing and confirmation that every
  configured layer exists at the pinned revision. `uv` and Docker are unavailable in this
  environment, so the exact `uv run` commands and a real container build remain pending.
- MacBook, Imager and Pi checkpoint: Pending focused closure and the checkpoint candidate. On
  the M1 Pro, run `./scripts/build-pi-image coordinator`, verify the printed manifest digest, flash
  the printed `.img` with Raspberry Pi Imager and confirm a Raspberry Pi 4 Model B reaches a normal
  boot. Record the command, artifact SHA-256, Imager result and boot result here before acceptance.
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

- Finding dispositions: Accepted both required findings. The exit cleanup now removes both final
  names until publication completes, including failed first or second moves and handled
  interruptions. Focused tests cover both move failures, a `TERM` between moves, Docker daemon
  failure and rejection of an x86_64 builder container. The source-string brittleness observation
  remains optional and did not expand this workstream.
- Simplification/deletion pass: Publication uses the existing staging directory, one success bit
  and one cleanup function. It adds no lock, transaction wrapper or compatibility path. Test setup
  now shares the small fake-repository and fake-Docker helpers instead of repeating them.
- Final verification: `bash -n scripts/build-pi-image`, `.venv/bin/pytest
  hosts/tests/test_pi_image_build.py` (15 passed), `.venv/bin/ruff check
  hosts/tests/test_pi_image_build.py` and `git diff --check` pass. The exact `uv run` equivalents,
  real Docker build and hardware checkpoint remain pending in the recorded environments.

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
- Accepted commit: Pending checkpoint candidate and hardware result.
