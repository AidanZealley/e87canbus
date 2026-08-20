# Raspberry Pi image-building implementation plan

Status: draft; implementation has not started.

## Orchestration record

- Integration branch: `feature/pi-image-building`
- Starting commit: `TBD`
- Orchestrator: `TBD`
- Specification approved at commit: `TBD`
- Started: `TBD`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Docker builder](01-docker-builder.md) | Approved spec | Not started | TBD |
| 2 | [Common host image](02-common-host.md) | 1 accepted | Not started | TBD |
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
| TBD | None recorded | TBD | TBD | TBD |
