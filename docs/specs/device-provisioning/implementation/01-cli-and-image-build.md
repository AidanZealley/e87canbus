# Workstream 1: Establish the CLI boundary and preserve image building

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
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

