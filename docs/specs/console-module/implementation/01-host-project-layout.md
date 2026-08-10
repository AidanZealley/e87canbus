# Workstream 1: Establish the role-neutral host project

Status: not started.

## Task packet

### Outcome

The existing Python project and tests live under top-level `hosts/` instead of `coordinator/`.
Packaging, tooling, contract generation and CI use the new paths, while runtime behaviour and
Python import names remain unchanged.

### Scope

- Move `coordinator/src/e87canbus` to `hosts/src/e87canbus` and `coordinator/tests` to
  `hosts/tests` as one mechanical rename.
- Update `pyproject.toml` build, pytest, mypy and import-linter configuration for the new paths.
- Update Python tooling and contract-watcher source paths that refer to `coordinator/`.
- Update CI host-code paths and commands while preserving the existing check set.
- Update tests whose filesystem fixtures derive the package location.
- Remove the obsolete empty `coordinator/` directory.
- Preserve generated artifacts unless a path-only generator change legitimately regenerates them
  byte-for-byte.

### Non-goals

- Adding console runtime code or a new console entry point.
- Reorganizing existing `e87canbus` layers or renaming imports.
- Splitting the frontend or setup scripts.
- Updating explanatory documentation; workstream 5 owns documentation after final paths settle.
- Adding compatibility symlinks, import aliases or support for both old and new paths.

### Initial ownership

- `coordinator/**` moved to `hosts/**`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `scripts/watch_frontend_contracts.py`
- Other build/generation scripts only where a literal host-source path must change

Do not edit `frontend/**`, `deploy/**`, `devices/**` or product documentation. If an executable
frontend command necessarily consumes the moved Python source, change only its path/configuration
edge and record the exception.

### Required seams

- The installed distribution remains named `e87canbus` and existing imports remain
  `e87canbus.*`.
- Existing `car`, `bench` and `simulator` compositions remain unchanged.
- Later workstreams receive final `hosts/src/e87canbus` and `hosts/tests` paths.
- Root `uv` commands continue to work without callers knowing the physical package directory.

### Acceptance criteria

- `coordinator/` no longer exists and `hosts/` contains the same source and test population.
- The wheel configuration packages `hosts/src/e87canbus`.
- Pytest, mypy, Ruff and import-linter discover the moved code normally.
- Coordinator runtime, generated contracts and frontend remain behaviourally unchanged.
- CI contains no executable reference to `coordinator/src` or `coordinator/tests`.
- The diff is predominantly a rename plus necessary path edits, with no new abstraction.

### Targeted verification

```bash
uv sync --locked
uv run pytest -q
uv run mypy
uv run ruff check hosts scripts/watch_frontend_contracts.py
uv run lint-imports
uv run python scripts/generate_custom_protocol.py --check
cd frontend && pnpm install --frozen-lockfile && pnpm api:check && pnpm typecheck && pnpm test && pnpm build
```

Also inspect `git diff --summary` to confirm Git recognizes the source/test move and search
executable configuration for stale old paths. Documentation references are expected until
workstream 5.

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
