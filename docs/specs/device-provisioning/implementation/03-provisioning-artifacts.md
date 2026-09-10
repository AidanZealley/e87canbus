# Workstream 3: Build and validate provisioning artifacts

Status: accepted.

## Task packet

### Outcome

`e87ctl` can build validated coordinator and console ARM64 application bundles and exact
role-specific provisioning ZIPs from an image manifest and recovery package without writing a
disk.

### Scope

- Define strict v1 image-contract, application-manifest and provisioning-manifest models.
- Build role-specific ready-to-run virtual environments and frontend assets in a pinned ARM64
  Linux container.
- Publish manifest-backed `application-v1.tar.gz` artifacts in the specified ignored locations.
- Generate UUID device identities, role-constrained leaf certificates, hostnames and configuration.
- Create the exact provisioning ZIP entries for coordinator and console.
- Validate entry names, fields, roles, versions, sizes, digests, paths and storage reserves with
  bounded streaming reads.
- Add archive fixtures that prove rejection without relying only on source-string tests.

### Non-goals

- Installing artifacts on a Pi, writing removable media or implementing routine deploy/rollback.
- General archive extraction, arbitrary files, alternate compression formats or signing initial
  provisioning bundles.
- Adding the workstation package to the Pi application payload.

### Initial ownership

- Artifact, device-identity, application-build and bundle modules under `e87ctl/src/e87ctl/`
- ARM64 application-builder inputs under `e87ctl/`
- Focused tests and fixtures under `e87ctl/tests/`
- CLI wiring, package dependencies, `uv.lock` and artifact ignore rules as integration exceptions

### Required seams

- Consume the recovery types from workstream 2 without duplicating key parsing.
- Consume and extend the accepted image manifest contract used by workstream 1.
- Produce one fixed bundle contract that workstreams 4 and 6 both validate.
- Build output records dirty Git context but never requires a clean tree.

### Acceptance criteria

- Both role application archives are complete `linux-aarch64` releases with no first-boot build.
- The application archive cannot install outside its digest-named release directory.
- Leaf certificates have the exact URI SAN, EKU, validity rules and role binding.
- Both provisioning ZIPs contain exactly their allowed entries and complete per-entry digests.
- Duplicate, unknown, linked, traversal, oversized, corrupt and incompatible content fails before
  state changes.
- Private keys and passwords are absent from manifests, output, logs and generated frontend assets.
- The pinned build container and output provenance are explicit and tested without requiring Docker
  in the focused suite.

### Targeted verification

```bash
uv run pytest e87ctl/tests -q
uv run ruff check e87ctl
uv run mypy
cd frontend && pnpm api:check && pnpm build
```

## Implementation handoff

- Base commit: `e00c939d7ce6f4a94d5dad3cfaaee1ecb1ec033c`
- Outcome: Added strict v1 image, application and provisioning artifact contracts. The workstation
  builder produces complete role-specific ARM64 virtual environments and frontend assets, while
  the provisioning builder creates a fresh device identity and the exact coordinator or console
  ZIP without touching a disk. Shared validators reject the full archive before a later writer or
  first-boot consumer changes state.
- Files changed: Added `e87ctl/src/e87ctl/{artifacts,application,provisioning}.py`, the pinned
  `e87ctl/application-builder/` container inputs and
  `e87ctl/tests/test_provisioning_artifacts.py`; extended `.gitignore` for local application
  outputs; and updated this record and the plan status.
- Decisions and frozen schema versions: Image, application and provisioning documents all use
  strict format version 1 and provisioning interface version 1. The image contract extends the
  accepted manifest with `provisioning_interface_version`, `boot_partition_size_bytes` and
  `root_filesystem_size_bytes`. Application archives contain `manifest.json` first, followed only
  by manifest-listed regular files beneath `venv/` and `frontend/`; their manifest binds role,
  `linux-aarch64`, Python 3.13, interface version, Git context, the pinned builder base and the
  complete builder-input digest. Provisioning manifests bind image and application versions,
  installation, UUIDv4 device identity, hostname, application digest and every non-manifest ZIP
  entry. The manifest cannot include its own digest without a circular document; validators
  instead require it as the first bounded entry and digest every payload entry.
- Generated artifacts and provenance: `build_application()` publishes
  `artifacts/applications/<role>/application-v1.tar.gz` atomically. The container uses the accepted
  digest-pinned ARM64 Trixie base, dated Debian snapshots, exact pnpm 9.15.1 and the frontend
  lockfile. It exports hashed runtime and build-only requirements from the root `uv.lock`, builds
  the project wheel without build isolation, installs only runtime dependencies into the copied
  Python 3.13 virtual environment and makes its two entry points relocatable. It builds only the
  selected frontend and excludes host `node_modules` and stale `dist` trees. The manifest records
  the current commit, dirtiness, builder-input digest and both lockfile digests without requiring a
  clean checkout. No generated artifact was retained during focused verification.
- Verification: `uv run pytest e87ctl/tests -q` passed with 86 tests; `uv run ruff check e87ctl`,
  `uv run mypy` with 138 source files, `bash -n e87ctl/application-builder/build-application` and
  `git diff --check` passed. `cd frontend && pnpm api:check && pnpm build` passed for both frontend
  applications. Behavioral TAR and ZIP fixtures cover traversal, absolute paths, links,
  duplicates, unknown entries, corruption, incompatible roles and both storage reserves. Focused
  certificate checks cover URI identity, role EKU, CA binding, validity, coordinator IP and DNS
  names and the console PKCS#12 chain.
- Known limitations or external checks: Docker and a full ARM64 application build were not run in
  this environment. The focused suite checks the pinned build inputs and packages representative
  ready-to-run payload trees without Docker. Workstream 3 has no external validation gate; the
  documented macOS and Pi checks remain owned by workstreams 4 and 7.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws3_review`), fresh independent reviewer.
- Verdict: Changes required. The schemas, archive rejection rules, device identities and generated
  certificate profiles are sound, but the application payload is not ready to run after install,
  its Python dependency build is not pinned, and provisioning construction does not keep large
  artifact reads bounded.
- Required findings:
  1. `e87ctl/application-builder/build-application` creates the virtual environment at
     `/output/venv` and packages it for installation under
     `/opt/e87canbus/releases/<application-digest>/venv`. Python console scripts retain their
     creation-time shebang, such as `#!/output/venv/bin/python3`, so both `e87canbus` entry points
     fail once the archive moves into its digest-named release. Build the environment for its final
     executable path, or apply one equally direct relocation-safe approach, and add a behavioral
     test that runs a packaged entry point after moving the payload.
  2. The builder installs the project with `pip install /source`. This resolves the root project's
     lower-bounded runtime dependencies and unpinned PEP 517 build requirements against mutable
     package indexes, without consuming `uv.lock`. The same commit and recorded builder digest can
     therefore produce a different dependency set. Make the Python environment consume the
     repository's locked dependency set and include every added builder input in the recorded
     provenance.
  3. `_provisioning_entries()` reads the allowed application archive into one `bytes` value with
     `application_path.read_bytes()`, then `_write_zip()` passes that value to `writestr`. A valid
     application may be 1 GiB, so provisioning requires an unbounded-in-practice allocation and
     contradicts this workstream's bounded streaming-read criterion. Stream the application file
     into the ZIP while retaining the existing size, digest and completed-archive validation.
- Optional observations: None.
- Questions for orchestrator: None.
- Verification: `uv run pytest e87ctl/tests -q` passed (`83 passed`); `uv run ruff check e87ctl`,
  `uv run mypy` (`138 source files`), `bash -n e87ctl/application-builder/build-application`,
  `cd frontend && pnpm api:check && pnpm build`, and `git diff --check` passed. A relocation probe
  created an environment under `output/venv`, installed the project, moved `output` to `release`
  and confirmed that `release/venv/bin/e87canbus` exits `127` because its interpreter path still
  names `output/venv`. Review also inspected every tracked and untracked workstream file, both
  accepted dependency handoffs and the exact TAR, ZIP, CA, leaf-certificate, PKCS#12, role,
  reserve, provenance and secret-exclusion paths. Docker and a full ARM64 build were not run.

## Resolution

- Finding dispositions: Accepted all three required findings. The builder rewrites only the two
  shipped Python entry points to locate `python3` beside themselves, so their creation-time
  `/output/venv` shebangs cannot escape into the installed release. It exports separate hashed
  runtime and `application-build` requirement sets from the repository `uv.lock`; a build-only
  virtual environment creates the wheel without PEP 517 isolation, and the published environment
  receives the locked runtime set plus that wheel with dependency resolution disabled. The root
  lockfile now owns Hatchling and its build dependencies. Provisioning keeps
  `application.tar.gz` as a validated `Path`, calculates its manifest record by streaming and
  writes it to the ZIP in bounded 1 MiB chunks before the existing completed-archive validation.
- Simplification/deletion pass: Kept one root lockfile and generates both temporary requirements
  exports at build time; no committed requirements files or parallel dependency list were added.
  The relocation helper handles only paths named by the builder and replaces the invalid shebang
  rather than adding wrapper entry points. The ZIP writer's existing entry value now accepts
  either the one path-backed application or the small in-memory configuration entries, avoiding a
  second archive construction path. No compatibility flags or fallback installers were added.
- Final verification: `uv sync --locked`; `uv run pytest e87ctl/tests -q` (`86 passed`); `uv run
  ruff check e87ctl`; `uv run mypy` (`138 source files`); `bash -n
  e87ctl/application-builder/build-application`; `cd frontend && pnpm api:check && pnpm build`;
  and `git diff --check` passed. New focused tests run a packaged entry point after moving it below
  `/opt/e87canbus/releases/<digest>`, verify the hashed runtime and build-only lock exports and
  reject any attempt to read the application TAR through `Path.read_bytes()` during provisioning.

## Closure review

- Verdict: Accepted. All three required findings are closed. The entry-point helper replaces only
  the two shipped Python shebangs with a sibling-`python3` launcher; both the focused packaged
  fixture and a relocated copy of the real `e87canbus` environment ran after their original path
  disappeared. The builder exports hashed runtime and `application-build` requirements from the
  locked root environment, installs Hatchling and its locked dependencies before a
  no-build-isolation wheel build, and records the Python and frontend lockfile digests beside the
  builder digest. The runtime export excludes the root project and workstation-only `e87ctl`.
  Provisioning now keeps the application as a `Path`, hashes and writes it with sized streaming
  loops, preserves the manifest record, and validates the completed ZIP as before.
- Remaining required findings: None. The remediation added no second dependency list, wrapper
  entry point or alternate archive path, and no release-blocking defect was introduced.
- Closure verification: `uv sync --locked`; `uv run pytest e87ctl/tests -q` (`86 passed`); `uv run
  ruff check e87ctl`; `uv run mypy` (`138 source files`); shell syntax for the application builder;
  both locked exports and their hashes; the relocated real entry-point probe; `cd frontend && pnpm
  api:check && pnpm build`; and `git diff --check` passed. Docker and a full ARM64 application build
  remain the already recorded non-gate limitation.
- Accepted commit: `fff702367bed156640f52085d6cc5c48ba196815`

## Reopened contract correction

- Trigger: Workstream 4 found that the approved provisioning flow requires the operator to select
  `car` or `bench`, but the accepted strict device configuration had no field that could carry the
  selection. This changes the public bundle contract and met the documented reopening condition.
- Correction: `DeviceConfiguration.deployment_profile` is required and accepts exactly `car` or
  `bench`. `build_provisioning_bundle()` requires the typed value and writes it to
  `configuration/device.json`. The existing provisioning-manifest size and SHA-256 record for that
  entry binds the selection without duplicating it in the manifest or adding a profile framework.
- Files changed: `e87ctl/src/e87ctl/provisioning.py`,
  `e87ctl/tests/test_provisioning_artifacts.py`, this record and the plan status. Workstream 4's
  reset record remains orchestrator-owned.
- Verification: `uv run pytest e87ctl/tests -q` passed (`88 passed`); `uv run ruff check e87ctl`,
  `uv run mypy` (`138 source files`) and `git diff --check` passed. Focused role-bundle cases cover
  both profiles and prove that a missing or unknown profile fails strict model validation.
- Specification drift: None. The correction carries an already approved required selection and
  introduces no new profile behavior.
- Focused closure: Codex (`/root/ws3_review`), original independent reviewer. Accepted. The public
  builder now requires `deployment_profile`, the strict configuration accepts only `car` or
  `bench`, and both roles serialize both accepted values into `configuration/device.json`.
  Provisioning validation checks that entry against its manifest size and SHA-256 before parsing
  the strict model, so missing, unknown or changed values fail without a duplicate profile field.
  No release blocker was introduced. The focused artifact tests passed (`29 passed`), the full
  `e87ctl` suite passed (`88 passed`), Ruff and mypy passed, all Python call sites supply the
  required value and `git diff --check` passed.
- Accepted correction commit: `924514ea061bb69a825efe19ebfec742c698bdf6`.
