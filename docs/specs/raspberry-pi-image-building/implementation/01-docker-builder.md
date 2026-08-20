# Workstream 1: Docker builder and base-image proof

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Pins and privilege model: `TBD`
- Verification: `TBD`
- MacBook, Imager and Pi checkpoint: `TBD`
- Known limitations: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`
