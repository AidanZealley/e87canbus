# Coordinator panel whole-feature review

Status: closure review. All workstreams 1–5 are accepted.

## Reviewer task packet

Review the complete implementation branch against the starting commit recorded in
[plan.md](plan.md), the [context](../context.md), and the [specification](../spec.md). Read every
accepted workstream handoff, but independently inspect the combined diff and surrounding code.

This is a whole-feature review, not permission to expand the feature. Evaluate:

- Completeness against every specification acceptance criterion.
- One shared panel service, hotspot service, and display derivation in production and simulation.
- The absence of panel/hotspot knowledge in the coordinator kernel.
- Correct dependency direction and thin seams at snapshots, backends, UART, and frontend state.
- Cross-workstream lifecycle behaviour at startup, readiness, fatal state, button handling, and
  graceful shutdown.
- Agreement between Python UART output, firmware parsing, setup paths, packages, permissions, and
  documentation.
- Whether failures remain isolated from coordinator readiness and CAN processing.
- Type safety, readable top-level control flow, and repository convention fit.
- Simplification opportunities created only by combining the workstreams: duplicated state,
  adapters with no second implementation, façade exports, obsolete mocks, speculative recovery,
  excessive configuration, and tests coupled to implementation details.

Run verification proportional to the assembled change. Broad repository checks are appropriate
here if they are part of normal project validation, but do not invent exhaustive fault matrices.
Never claim physical validation without evidence.

## Finding rules

Classify each item as `Required`, `Optional`, or `Question` using the definitions in
[README.md](README.md). Required findings include evidence, consequence, the violated requirement
or risk, and the smallest coherent correction. Group findings by owning workstream.

Do not edit implementation files. Complete the review record below and return the verdict to the
orchestrator.

## Initial whole-feature review

- Reviewer: `Codex /root/whole_feature_review`
- Branch and starting commit: `feature/coordinator-panel-implementation` from
  `6179d6f8d23a1dc5b7c34d3fc5c739c053f255dc`.
- Reviewed head: `29e9cad1e56d7518e89998ed2e2d8dfed344446e`.
- Verification run:
  - `uv run pytest` completed with 833 passed and one failed: the stale simulator OpenAPI
    operation-count assertion recorded below.
  - `uv run ruff check .`, `uv run mypy coordinator/src/e87canbus`, `uv run lint-imports`,
    `uv run python scripts/generate_custom_protocol.py --check`, and `uv lock --check` passed; both
    import contracts were kept.
  - `pnpm test` passed all 158 tests in 35 files; `pnpm typecheck`, `pnpm lint`, `pnpm api:check`,
    and `pnpm build` passed.
  - `uvx --from platformio pio test -e native` passed all four firmware tests and
    `uvx --from platformio pio run -e qtpy_rp2040` built successfully (40,092 bytes flash, 8,804
    bytes RAM).
  - Bash syntax checks passed for setup, upload, and the fixed hotspot helper; executable-bit and
    `git diff --check` checks passed. Setup and upload were not run against this development host.
- Acceptance-criteria audit:
  - All six semantic displays and the complete hotspot button table, including starting
    cancellation, client connect/disconnect, failed-operation retry, readiness gating, and reset,
    run through `PanelService` and `HotspotService` in the composed simulator path. React contains
    only semantic appearance mapping and calls the simulator commands; it owns no transition or
    priority rule.
  - Production and simulation use the same typed services and display derivation. Production adds
    only the fixed UART and NetworkManager edges; simulation adds only in-memory edges. The combined
    diff makes no kernel or domain change and projects the existing read-only controller snapshot
    from runner composition.
  - Physical lifecycle starts outside the controller owner, keeps the one-second UART owner
    independent of bounded NetworkManager work, captures readiness with each complete button event,
    reports fatal health through the display, sends graceful `off` before UART close when possible,
    and converts unexpected accessory failure to heartbeat loss without changing controller
    readiness or CAN processing.
  - Python sends exactly `STATUS <display>\n` for the frozen six-value vocabulary over
    `/dev/serial0` at 115,200 baud and accepts only bounded complete `BUTTON\n` lines. Firmware uses
    the same vocabulary and baud rate on the labelled QT Py TX/RX pins, owns exactly five A3 pixels,
    uses A0 with pull-up, caps every channel at 127, debounces presses, and implements the 60-second
    first-status timeout, three-second established timeout, immediate valid-status recovery, and
    graceful-off latch.
  - Physical setup is limited to the approved Raspberry Pi 4 `car` and `bench` profiles. It enables
    `/dev/serial0`, removes the serial console, grants `dialout`, installs NetworkManager and `iw`,
    reconciles only `e87canbus-hotspot`, preserves or silently replaces its password without argv,
    environment, log, or repository exposure, disables autoconnect and the active connection, and
    grants only four exact root-owned helper actions. Simulator setup bypasses those changes.
    Firmware upload, harness safety, permissions, commands, and all unresolved bench checks agree
    across setup, device, deployment, and wiring documentation.
  - The implementation otherwise satisfies the software acceptance criteria and preserves every
    explicit non-goal. Physical Pi, UART, pixel, button, hotspot-client, cancellation, forwarding,
    and upload behaviour remains correctly documented as pending rather than claimed. The branch is
    not ready for acceptance until the required repository-test correction below is made.
- Required findings by owner:
  - Workstream 2, simulator integration: `coordinator/tests/test_openapi_contract.py:27` still
    asserts that the full simulator schema has 39 operations, although this workstream deliberately
    added six coordinator-panel operations and the generated schema now contains 45. The broad
    `uv run pytest` run therefore fails with `assert 45 == 39`, despite the generated OpenAPI/client
    checks passing. This leaves normal repository verification red and makes the stable-operation-ID
    guard inconsistent with the accepted API surface. Update the expected operation count to 45
    and add one representative coordinator-panel operation ID to the existing assertions so the
    guard acknowledges the intentional surface while continuing to protect uniqueness; rerun the
    full Python suite and generated-contract checks.
- Optional observations: `None`.
- Questions for orchestrator: `None`.
- Verdict: `Changes required`.

## Orchestrator triage

- Accepted required findings and assigned owners: Accepted the stale OpenAPI operation-count
  assertion and assigned it to the Workstream 2 implementation owner. The six intentional panel
  routes bring the full simulator operation count from 39 to 45; the contract test must reflect the
  shipped surface and protect one representative panel operation ID.
- Rejected findings and reasons: `None`.
- Deferred optional observations: `None`.
- Specification drift requiring Aidan's decision: `None`.

Each affected owner receives all of its accepted findings together and performs one coherent pass.
Owners update their workstream `Resolution` with the additional final-review work and verification.

## Focused closure

The same final reviewer verifies only the orchestrator-accepted findings and checks that their
corrections introduced no release-blocking defect. It does not conduct a second open-ended review.

- Reviewed head: `29e9cad1e56d7518e89998ed2e2d8dfed344446e` plus the uncommitted accepted
  Workstream 2 correction and workflow records in the working tree.
- Finding outcomes: `Accepted`. `coordinator/tests/test_openapi_contract.py` now expects the 45
  operations in the full simulator schema and asserts the representative
  `getSimulationCoordinatorPanel` operation ID while retaining the uniqueness and existing surface
  checks. The focused contract file passed all three tests; `uv run pytest` passed all 834 tests;
  `pnpm api:check` reproduced the OpenAPI, HTTP client, button catalogue, and live contracts cleanly;
  focused Ruff and `git diff --check` passed.
- Final simplification assessment: The correction changes only the two stale assertions in the
  existing stable-operation-ID test. It adds no implementation code, compatibility path, duplicate
  contract, or test machinery, and introduces no release-blocking defect.
- Remaining blockers: `None`.
- Verdict: `Accepted`.

## Orchestrator completion record

- Final head: `TBD`
- Final verification: `TBD`
- Hardware validation still pending: `TBD`
- Specification drift: `TBD`
- Completion report delivered: `TBD`
