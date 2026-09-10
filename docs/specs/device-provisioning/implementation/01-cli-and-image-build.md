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
- Accepted commit: `TBD`
