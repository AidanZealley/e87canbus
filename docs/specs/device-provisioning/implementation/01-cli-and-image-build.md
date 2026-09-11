# Workstream 1: Establish the CLI boundary and preserve image building

Status: closure review.

## Task packet

### Outcome

`uv run e87ctl image build coordinator|console` is the only repository image-build interface. The
new top-level workstation package exists, while both existing Pi runtime commands remain unchanged.

### Scope

- Create the typed `e87ctl` package, entry point and minimal subcommand dispatch.
- Expose it as an editable local dependency from the root uv development environment.
- Move `scripts/build-pi-image` and its focused tests beneath `e87ctl`.
- Wrap the shell implementation from `e87ctl image build` without rewriting its Docker logic.
- Update CI, image documentation and live references to the new public command and path.
- Remove the obsolete root script path and stale aliases.

### Non-goals

- Installation identities, artifacts, disk writing or placeholder implementations of later
  commands.
- A uv workspace, plugin system or generic command framework.
- Changes to the accepted Docker builder or Pi image contents unless required by the move.

### Initial ownership

- `e87ctl/pyproject.toml`
- `e87ctl/src/e87ctl/`
- `e87ctl/scripts/build-pi-image`
- `e87ctl/tests/test_image_build.py`
- Root `pyproject.toml`, `uv.lock` and `.github/workflows/ci.yml`
- `scripts/build-pi-image` and `hosts/tests/test_pi_image_build.py` for removal
- Image-build command references in `images/README.md`, `docs/setup.md` and `deploy/README.md`

### Required seams

- Later subcommands must attach to one small typed CLI without importing host-runtime internals.
- The wrapper must preserve current arguments, Docker mounts, cache behavior, artifacts and
  manifest semantics.
- The root environment must run the package while application bundle construction can exclude it.

### Acceptance criteria

- Both public commands reach the accepted shell builder and invalid roles fail clearly.
- The old public script and host-package image tests are gone.
- Existing image-builder tests retain their meaningful behavior at the new location.
- `e87canbus` and `e87canbus-console` entry points and packages are unchanged.
- CI checks both packages without introducing a second lockfile policy or duplicated tool config.

### Targeted verification

```bash
uv sync --locked
uv run e87ctl --help
uv run e87ctl image build --help
uv run pytest e87ctl/tests/test_image_build.py -q
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run mypy
bash -n e87ctl/scripts/build-pi-image
```

## Implementation handoff

- Base commit: `0c939f34335708b4e6370d2a68f7cfe6b06b71f3`
- Outcome: Added the top-level `e87ctl` package and made `uv run e87ctl image build
  coordinator|console` the only live image-build interface. The command invokes the relocated
  builder with its Docker, cache, artifact and manifest behavior unchanged.
- Files changed: Added `e87ctl/pyproject.toml`, `e87ctl/src/e87ctl/{__init__,cli}.py`,
  `e87ctl/scripts/build-pi-image` and `e87ctl/tests/test_image_build.py`; removed the former root
  script and host test; updated the root package metadata, lockfile, CI and the three owned
  image-build references.
- Decisions: Used stdlib `argparse` and direct subprocess invocation. `e87ctl` is an editable
  development dependency, so the runtime wheel and its two existing entry points remain unchanged.
  Root pytest, Ruff and mypy configuration covers both packages without a second lockfile or
  duplicated tool settings.
- Verification: All targeted commands passed: `uv sync --locked`; both required help commands;
  `uv run pytest e87ctl/tests/test_image_build.py -q` (`41 passed`); `uv run ruff check e87ctl
  hosts scripts/watch_frontend_contracts.py`; `uv run mypy` (`132 source files`); and `bash -n
  e87ctl/scripts/build-pi-image`. The full Python suite passed (`886 passed`), the real CLI rejected
  an invalid role with exit code 2, and `git diff --check` passed.
- Known limitations or external checks: Docker and arm64 image builds were not run. This
  workstream only moves the previously accepted builder and has no external validation gate.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws1_review`), fresh independent reviewer.
- Verdict: Accepted. The uncommitted workstream satisfies its task packet and preserves the
  accepted image builder without opening later lifecycle scope.
- Required findings: None. The relocated shell builder differs from the accepted version only in
  its repository-root lookup. Both public roles dispatch to that executable, invalid roles fail
  through `argparse` with exit code 2, and the old script and host-test paths are removed. The root
  editable dependency exposes `e87ctl` without changing the `e87canbus` or `e87canbus-console`
  entry points or including the workstation package in the runtime wheel. CI and root tool
  configuration cover both source trees with one lockfile.
- Optional observations: None.
- Questions for orchestrator: None.
- Verification: `uv sync --locked`; both required help commands; `uv run pytest
  e87ctl/tests/test_image_build.py -q` (`41 passed`); `uv run pytest -q` (`886 passed`); `uv run
  ruff check e87ctl hosts scripts/watch_frontend_contracts.py`; `uv run mypy` (`132 source files`);
  `bash -n e87ctl/scripts/build-pi-image`; the real CLI invalid-role check; standalone `e87ctl`
  wheel construction; and `git diff --check` passed. Review also compared the moved builder and
  test file against `HEAD`, inspected every untracked `e87ctl` source file and audited live
  references to the obsolete paths. Docker and arm64 image builds were not repeated because the
  accepted builder implementation did not change and this workstream has no external gate.

## Resolution

- Finding dispositions: The independent review found no required findings, optional observations
  or questions. No remediation pass was needed.
- Simplification/deletion pass: Kept the accepted shell builder instead of duplicating its Docker
  logic in Python. Removed the obsolete root script and host-package test, and removed an
  unnecessary `python -m e87ctl` alias before review. The remaining CLI uses stdlib `argparse`, one
  direct subprocess call and the root repository's existing test and type-check configuration.
- Final verification: No implementation changed after independent review. The implementation and
  reviewer both passed the targeted commands, the full Python suite (`886 passed`), the real
  invalid-role check and `git diff --check`. The reviewer also built the standalone `e87ctl` wheel
  and audited the moved files and live path references.

## Closure review

- Verdict: Accepted. No implementation changed after the independent review. The resolution
  accurately records that no remediation was required, and the status updates introduce no
  release-blocking defect.
- Remaining required findings: None.
- Accepted commit: `3a1f0a2a0b65ae96b31d7be13281619408cbc7eb`

## macOS gate attempt 1 correction

- Status: Accepted.
- Owner and base: Codex (`/root/ws1_snapshot_fix`), working from
  `c7e21f0ef275cf1adbc5ad5ddfdbb894ee231423`.
- Reopening reason: The first macOS writer-gate attempt could not produce a compatible image.
  Both builds used their launch time for Debian snapshots instead of the pinned
  `PACKAGE_SNAPSHOT_EPOCH=1786579200`, then failed while the live `trixie-security` snapshot was
  incomplete. The Docker environment contained `SOURCE_DATE_EPOCH`, but pinned upstream commit
  `262d4df5a9f9d4133370465399a7958a7c22cdc7` creates its generated configuration through `env -i`.
- Correction: Pass `SOURCE_DATE_EPOCH=1786579200` as an upstream build configuration override
  after `--`, alongside the existing `IGconf_*` overrides. Remove the ineffective Docker-only
  environment option. Add the standard `images/post-build.sh` source hook, which checks the
  assembled root's generated `/usr/share/rpi-image-gen/origin` for the exact epoch before image
  generation and deployment can publish an artifact.
- Upstream contract checked: At the pinned revision, `rpi-image-gen` writes command-line overrides
  into its generated `final.env`, invokes build phases from that environment, and its `snapgen`
  generator records `# SOURCE_DATE_EPOCH: <value>` in `rpi-image-gen.origin`. The built-in cleanup
  phase copies that record into the assembled root before the source `post-build.sh` hook runs.
  Upstream's reproducible-build examples use the same `-- SOURCE_DATE_EPOCH=<epoch>` form.
- Files changed: `e87ctl/scripts/build-pi-image`, `e87ctl/tests/test_image_build.py`, and the new
  `images/post-build.sh`, plus this record and `plan.md`.
- Test evidence: The fake-Docker build records the complete final `docker run` argument vector and
  proves the epoch appears only after the upstream `--` separator. A focused executable-hook test
  accepts the pinned generated origin and rejects an origin produced by the live-time fallback.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py -q` passed (`43 passed`), and the
  complete `e87ctl` suite passed (`117 passed`). `uv run ruff check e87ctl`, `uv run mypy` over 143
  source files, shell syntax checks for the builder, post-build hook, image hooks and image checker,
  and `git diff --check` passed.
- External check: Docker is unavailable in this environment, so the correction does not claim a
  real image build. The macOS writer gate remains `Troubleshooting` until a committed candidate
  produces a compatible image and passes the recorded gate evidence.
- Simplification and drift: The correction uses upstream's existing configuration and hook
  contracts. It adds no upstream patch, fork, fallback timestamp or second snapshot setting.
  Specification drift: None.

### Focused correction review and resolution

- Reviewer and verdict: Claude Code Opus at medium effort through the configured read-only review
  command. Accepted with one required test correction.
- Required finding: The hook behavior test invoked `images/post-build.sh` through `sh`, but the
  pinned upstream runner ignores a source hook that lacks executable mode. The test therefore did
  not protect the hook-discovery contract.
- Optional observation accepted: Pin the existing `-S /source/images` argument in the recorded
  Docker invocation because that directory is where upstream discovers `post-build.sh`.
- Resolution: The test now asserts `os.access(SNAPSHOT_CHECK, os.X_OK)` and the exact source-root
  argument. Git records `images/post-build.sh` as mode `100755`. The runbook briefly states that the
  builder pins the Debian package snapshot and checks the generated origin before publication.
- Rejected or deferred observations: No test was added for the practically unreachable absent-env
  branch, and no multi-stanza parsing machinery was added. The exact generated epoch line already
  detects the observed live-time fallback.
- Simplification: Kept one upstream override, one standard post-build hook and one exact-line check.
  The correction still has no alternate timestamp path or upstream patch.

### Correction closure review

- Reviewer and base: Codex (`/root/ws1_snapshot_closure`), reviewing the complete uncommitted
  correction from `c7e21f0ef275cf1adbc5ad5ddfdbb894ee231423`.
- Accepted finding: Closed. `images/post-build.sh` is executable and resolves to Git mode `100755`.
  Its behavior test pins that executable contract. The recorded Docker argument test also pins
  `-S /source/images`, which is the source root where the upstream runner discovers the hook.
- Correction check: The final Docker invocation passes the exact
  `SOURCE_DATE_EPOCH=1786579200` after upstream's `--` separator and no longer uses Docker's
  `--env` path. At pinned upstream revision `262d4df5a9f9d4133370465399a7958a7c22cdc7`, command-line
  overrides enter the generated `final.env` across both `env -i` boundaries. `snapgen` writes the
  same value to `rpi-image-gen.origin`; built-in cleanup copies that file into the assembled root;
  and the source post-build hook checks its exact epoch line before SBOM, image generation and
  deployment.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py -q` passed (`43 passed`); `uv run
  ruff check e87ctl`, shell syntax checks for the builder and hook, and both tracked and new-file
  whitespace checks passed. Direct executable-hook checks accepted the pinned origin and rejected
  both the live-time fallback and an absent generated epoch. Docker remains unavailable, so the
  macOS writer gate still owns the real image-build evidence.
- Remaining required findings: None. The remediation introduced no release-blocking defect.
- Verdict: Accepted.
- Accepted correction commit: `d0a22c191e8402602f299ec2b77006c9a59e400d`.

## macOS gate attempt 2 correction

- Status: Closure review.
- Owner and base: Codex (`/root/ws1_snapshot_fix`), working from
  `f9e81f608c849e30b32bb56cee4b5b7eb70c915e`.
- Reopening reason and decision: Attempt 2 proved the accepted epoch propagation worked, then apt
  rejected the old security snapshot because pinned upstream writes an ineffective one-line
  `Options:` field into its deb822 source. Aidan accepted package drift between devices and releases
  and accepted reprovisioning all devices if a package-version problem occurs. That decision
  supersedes the attempt 1 snapshot correction.
- Correction: Select pinned upstream's `debian-trixie-arm64-minbase-rolling` target layer. Remove
  `PACKAGE_SNAPSHOT_EPOCH`, its generated-configuration override, `images/post-build.sh`, its
  behavioral tests and the snapshot-specific runbook claim. Keep the pinned `rpi-image-gen`
  revision, digest-pinned builder container base and the builder container's existing apt source
  configuration because they are separate working tooling inputs.
- Tests and simplification: The existing builder-input test now pins the rolling target layer. The
  correction removes the fake-Docker argument recorder, snapshot hook tests and their supporting
  Python code. It adds no build-both command, pin-bump process, SBOM work, apt validity workaround
  or unrelated disk-diagnostic reorder.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py -q` passed (`41 passed`), and the
  complete `e87ctl` suite passed (`115 passed`). `uv run ruff check e87ctl`, `uv run mypy` over 143
  source files, shell syntax checks for the builder, role hooks and image checker, and
  `git diff --check` passed.
- External check and drift: Docker remains unavailable in this environment, so the macOS writer
  gate stays `Troubleshooting` pending a real rolling-layer image build and destructive-path
  evidence. Approved drift: target OS packages may vary between image builds; the image manifest
  and digest identify the produced artifact.

### Focused review

- Reviewer and verdict: Claude Code Opus at medium effort through the configured read-only review
  command. Accepted with no required findings.
- Evidence: The target selects pinned upstream's rolling Trixie minbase layer, and the correction
  fully removes the project epoch override, origin hook, supporting tests and runbook promise. The
  pinned builder revision, digest-pinned builder base and builder-container apt configuration stay
  intact. Focused and complete `e87ctl` tests, Ruff, mypy, shell syntax and diff checks passed.
- Optional observations rejected: Do not restore the `-S /source/images` assertion because its
  reason was the deleted source hook; existing image-build tests and the command retain the source
  root. Do not add another package-drift sentence to the runbook because this record and the plan
  already own that decision.
- Question recorded: Pinned upstream's rolling layer bootstraps through a launch-time snapshot, so
  a rare snapshot transition may require retry, but it has no permanent expiry and does not justify
  a project workaround.
- Remediation: None required. The deletion and simplification pass remains the reviewed result.

### Correction closure review

- Reviewer and base: Codex (`/root/ws1_rolling_closure`), reviewing the complete uncommitted
  correction from `f9e81f608c849e30b32bb56cee4b5b7eb70c915e`.
- Accepted findings: None. The focused review found no required issue and required no remediation.
- Correction check: `images/common/image.yaml` selects pinned upstream's
  `debian-trixie-arm64-minbase-rolling` layer. The historical epoch override, generated-origin hook,
  hook tests and snapshot runbook claim are gone. The pinned upstream revision, digest-pinned
  builder base, builder-container apt sources, image manifest and artifact digest remain. The diff
  adds no batch build, pin management, SBOM change or apt-validity workaround.
- External transient: The pinned rolling layer initially resolves a launch-time snapshot before
  replacing snapshot sources with rolling repositories in the target. A snapshot transition may
  require a retry. Per the accepted triage, this is an external transient rather than a project
  blocker and does not justify more builder machinery.
- Verification: `uv run pytest e87ctl/tests/test_image_build.py -q` passed (`41 passed`); the full
  `uv run pytest e87ctl/tests -q` suite passed (`115 passed`); Ruff and mypy passed; shell syntax
  checks passed for the builder, role hooks and image checker; the removed hook is absent; live
  image-builder sources contain no historical target-snapshot or SBOM machinery; and `git diff
  --check` passed. Docker is unavailable, so the existing macOS gate still owns the real build.
- Remaining required findings: None. The correction introduces no release-blocking defect.
- Verdict: Accepted.
