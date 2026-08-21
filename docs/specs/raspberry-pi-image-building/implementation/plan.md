# Raspberry Pi image-building implementation plan

Status: approved; implementation started.

## Orchestration record

- Integration branch: `feature/pi-image-building`
- Starting commit: `f2601794236cca66d71d7b6389a820fc5064312b`
- Orchestrator: Codex (`gpt-5.6-sol`, T3 Code)
- Specification approved at commit: `f2601794236cca66d71d7b6389a820fc5064312b`
- Started: `2026-08-20`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Docker builder](01-docker-builder.md) | Approved spec | Accepted | `7f78f3f` |
| 2 | [Common host image](02-common-host.md) | 1 accepted | Implementing | TBD |
| 3 | [Coordinator image](03-coordinator-image.md) | 2 accepted | Not started | TBD |
| 4 | [Console image](04-console-image.md) | 3 accepted | Not started | TBD |
| 5 | [Hardware acceptance](05-hardware-acceptance.md) | 3 and 4 accepted | Not started | TBD |

Use only `Not started`, `Implementing`, `Review`, `Remediation`, `Closure review` or `Accepted`.
Only one workstream may be active.

## Why these boundaries

Workstream 1 isolates the uncertain Docker Desktop and `rpi-image-gen` path before project image
work starts. Workstream 2 freezes shared packages, filesystem rules, artifact metadata and the
first-boot boundary. The coordinator and console then get separate vertical implementations because
their boot, CAN, network and display requirements differ. The last stream owns the operator
runbook and physical evidence instead of pretending remote checks prove a usable image.

## Cross-workstream contracts

- `./scripts/build-pi-image coordinator` and `./scripts/build-pi-image console` are the only public
  build commands.
- Images are arm64 Raspberry Pi OS Lite Trixie for Raspberry Pi 4 Model B.
- Outputs and manifests live below `artifacts/images/<role>/` and remain ignored by Git.
- The manifest contains the role, format version, Pi model, OS, architecture, builder revision,
  build time, Git context, dirty state, byte size and SHA-256 digest.
- Common image rules live in `images/common/`. Role workstreams do not silently rewrite them.
- Images contain no installation secrets, operator account, repository clone or current application
  bundle.
- The image may prepare a versioned first-boot service boundary, but it must not invent the final
  credential or application bundle formats owned by provisioning.
- Current setup scripts remain the working deployment fallback until the later provisioning CLI
  replaces them. Image work must identify duplicated behavior and keep it synchronized during this
  transition.

## Ownership handoffs

Workstream 1 owns the wrapper, container and manifest implementation. Later agents request changes
through the orchestrator. Workstream 2 owns common image configuration. Workstreams 3 and 4 consume
it and return shared defects to that owner. Ownership of the focused image test file passes
sequentially so each stream can add assertions for its own behavior.

Existing files under `deploy/` remain canonical runtime assets. Role image definitions should copy
or install them rather than fork their contents. Changes to those assets require an orchestrator
approved integration exception and the existing deployment tests.

## Whole-feature acceptance

- Every workstream is accepted and the branch is clean.
- The two public commands produce manifest-backed image artifacts.
- The base checkpoint passes on Docker Desktop, Raspberry Pi Imager and Raspberry Pi 4.
- Both final role images pass the recorded MacBook build and Pi 4 boot checks.
- Existing deployment behavior and focused image checks pass.
- The final reviewer finds no unresolved required issue or specification conflict.

## Decision and drift log

Before workstream 1, record the exact builder, container and package-source pins. Before
workstream 2, freeze the image side of the first-boot boundary without defining the later
provisioning bundle formats.

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-08-20 | Pin `rpi-image-gen` v2.8.0 at `262d4df5a9f9d4133370465399a7958a7c22cdc7`; pin the arm64 `debian:trixie-slim` manifest at `sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0`; use Debian and Debian Security snapshots at `20260813T000000Z`. Keep the upstream Raspberry Pi archive fixed to the `trixie` suite and `main` component. | These are the newest tagged builder and matching arm64 Trixie base at implementation start. Debian supports immutable dated snapshots. The Raspberry Pi archive has no equivalent snapshot endpoint, so its Trixie packages remain rolling and the manifest records the resulting image digest. | Approved specification delegated exact pins to workstream 1 | 1-5 |
