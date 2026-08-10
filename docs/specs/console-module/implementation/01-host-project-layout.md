# Workstream 1: Establish the role-neutral host project

Status: accepted.

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

- Base commit: `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`
- Outcome: Moved the unchanged `e87canbus` package and host tests from `coordinator/` to `hosts/`
  and updated every owned executable path edge; the obsolete directory is absent.
- Files changed: Renamed the complete tracked `coordinator/**` tree to `hosts/**`; updated
  `pyproject.toml`, `.github/workflows/ci.yml`, `scripts/generate_custom_protocol.py`,
  `scripts/watch_frontend_contracts.py`, the reload path and two path-sensitive tests.
- Decisions: Kept the distribution, imports, compositions and generated artifacts unchanged. Left
  documentation and two frontend source comments with old path wording for their assigned streams.
- Verification: Existing environment equivalents passed: 823 Python tests; strict mypy over 123
  files; Ruff; both import-linter contracts; custom protocol check; OpenAPI, HTTP and live contract
  checks; frontend typecheck; 158 frontend tests; production build. `pnpm install
  --frozen-lockfile` also passed. Diff inspection recognizes the source/test tree as renames and
  executable configuration outside documentation/frontend contains no old source/test path.
- Known limitations or external checks: Literal `uv sync --locked`, `uv run ...` and therefore the
  wrapper `pnpm api:check` could not run because `uv` is unavailable in this shell. Their Python
  and contract checks passed directly with the existing virtual environment and `hosts/src` on
  `PYTHONPATH`; rerun the literal commands in a `uv`-enabled environment.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws1_reviewer`)
- Verdict: Changes required in the durable workflow record only; the Workstream 1 implementation
  itself satisfies its frozen packet. Independent checks passed: 823 tests, strict mypy over 123
  source files, Ruff, both import-linter contracts, custom-protocol generation, OpenAPI/live
  contract generation, import discovery from `hosts/src`, and `git diff --check`. Rename inspection
  found only the three necessary path-sensitive source/test edits, and no stale executable
  `coordinator/src` or `coordinator/tests` reference remains outside documentation/frontend text
  assigned to later workstreams.
- Required findings: The recorded base
  `ec0ae8d428af230f347070bee37e5f532a092712` in this handoff and `plan.md` does not resolve to a
  commit. The branch's unchanged HEAD is
  `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5` (`Approve coordinator and console split
  implementation plan`). Correct both durable base records before acceptance so later branch and
  whole-feature diffs have an auditable starting point.
- Optional observations: None.
- Questions for orchestrator: None.

## Resolution

- Finding dispositions: Accepted and corrected the invalid full base hash in the plan's starting
  and specification-approved records and in this implementation handoff.
- Simplification/deletion pass: Kept remediation record-only; no implementation, compatibility
  path or additional workflow machinery was added.
- Final verification: `git rev-parse` resolves every corrected record to
  `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`; focused diff inspection confirms only the three base
  fields and this resolution record changed during remediation. `git diff --check` passes.

## Closure review

- Verdict: Pass. The accepted base-record finding is resolved: all three durable records now use
  the actual approved branch HEAD, `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`, and the hash
  resolves successfully. Focused diff inspection and `git diff --check` found no release-blocking
  defect introduced by the record-only remediation.
- Remaining required findings: None.
- Accepted commit: `5c1afaf1a73457ebc04f01060ffceaa9ac0befe7`
