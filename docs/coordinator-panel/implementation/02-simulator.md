# Workstream 2: simulator integration

Status: closure review.

## Task packet

### Outcome

Run the accepted shared panel and hotspot services in the simulator and make the existing frontend
card a pure renderer of their state. A user must be able to experience every agreed display and
hotspot transition without any separate simulator business rules.

### Scope

- Compose the shared services for the simulator using a minimal in-memory hotspot backend and panel
  output.
- Project the existing simulated `ControllerLoop` snapshot into the shared coordinator status.
- Add the smallest simulation-only API/state publication needed for the frontend card.
- Route the simulator button through the same panel-service method as physical `BUTTON` input.
- Add simulation controls for client connect/disconnect and hotspot failure/recovery.
- Remove component-local hotspot and display transition logic from
  `SimulatorCoordinatorPanel.tsx`.
- Regenerate checked-in API clients/contracts through repository scripts when the selected API seam
  requires it; do not hand-edit generated output.
- Add focused backend and frontend tests for the complete simulator path.

Choose the simplest existing API mechanism that keeps the frontend current. Do not add a second
live-publication architecture solely for this card. Record the choice and why it is smaller than
the directly available alternatives.

### Non-goals

- Serial ports, UART messages, NetworkManager, `nmcli`, RP2040 execution, or electrical simulation.
- A simulated network topology, leases, client identities, or retry timing.
- Business rules in React or simulator routes.
- Kernel state, inputs, commits, effects, or topics for the panel.

### Initial ownership

- Minimal in-memory implementations under `coordinator/src/e87canbus/runners/simulation/`.
- Simulation-only routes/models/commands needed for panel controls.
- Necessary application composition/lifecycle seams for the simulated accessory services.
- Existing coordinator-panel and simulator-workbench frontend components.
- Generated API artifacts required by the chosen endpoint changes.
- Focused simulator/API/frontend tests.
- This workstream record.

Do not modify shared product rules from workstream 1 without returning a defect to its owner through
the orchestrator.

### Required seams

- Existing simulated controller snapshot to shared `CoordinatorStatus`.
- Simulator button endpoint to shared panel-service button operation.
- Development controls to in-memory backend observations only.
- Shared `PanelDisplay` snapshot to the React renderer.

### Acceptance criteria

- Production and simulator rules have one Python implementation.
- React contains appearance mapping only; it contains no hotspot transition or priority rules.
- All six displays are reachable through causes, not direct arbitrary LED colours.
- A second press while starting cancels activation through the shared service.
- Client and failure controls affect the in-memory backend and flow through shared derivation.
- Reset creates a clean disabled-hotspot state consistent with simulator session reset behaviour.
- No kernel changes are made.

### Targeted verification

The agent records exact new test paths selected from the final change. At minimum run the known
affected suites, frontend type checking, and generated-contract checks:

```bash
uv run pytest coordinator/tests/test_simulator_api.py coordinator/tests/test_deployment_profiles.py
(cd frontend && pnpm test src/components/coordinator-panel/CoordinatorPanel.test.tsx \
  src/components/simulator-workbench/SimulatorCoordinatorPanel.test.tsx)
(cd frontend && pnpm typecheck)
(cd frontend && pnpm api:check)
```

Also run each new focused backend or frontend test file not covered above. Record every command and
result.

## Implementation handoff

- Base commit: `27c1d39d85778dc76fe97b6635c9b5e7e003cb22`
- Outcome: Composed the accepted panel and hotspot services for the full simulator profile with
  in-memory output and hotspot edges, projected the real controller-loop snapshot into the panel,
  added simulator controls for every agreed cause and transition, reset accessory state with each
  simulator session, and replaced the React card's local rules with shared-service state.
- Files changed: `coordinator/src/e87canbus/api/main.py`,
  `coordinator/src/e87canbus/runners/simulation/coordinator_panel.py`, simulator API installation,
  coordinator-panel routes and models under `coordinator/src/e87canbus/runners/simulation/api/`,
  `coordinator/tests/test_simulator_api.py`, `coordinator/tests/test_deployment_profiles.py`,
  `frontend/src/components/simulator-workbench/SimulatorCoordinatorPanel.tsx` and its test,
  generated HTTP client files under `frontend/src/api/http/`, `protocol/openapi.json`, and this
  record.
- API/publication choice: Added one simulation-only HTTP snapshot plus command endpoints and used
  the repository's existing generated TanStack Query client with a 500 ms refresh. Mutation
  responses update the same query immediately. This avoids adding the panel to the kernel's live
  topics or creating a second socket publication path for one development-only card.
- Decisions: The in-memory backend exposes only observable activation, client, and command-failure
  causes. A narrow coordinator-condition preview accepts `CoordinatorStatus`, never
  `PanelDisplay`, so all six appearances can be experienced while display priority remains solely
  in `PanelService`; its default and reset value is the live `ControllerLoop` projection. A
  simulator session-id change rebuilds the in-memory edges, giving reset a disabled hotspot without
  coupling the reset route to accessory rules.
- Verification: `uv run pytest coordinator/tests/test_simulator_api.py
  coordinator/tests/test_deployment_profiles.py` (51 passed); focused `uv run ruff check ...`
  (passed); `uv run mypy coordinator/src/e87canbus` (passed); `uv run lint-imports` (2 contracts
  kept); focused frontend `pnpm test src/components/coordinator-panel/CoordinatorPanel.test.tsx
  src/components/simulator-workbench/SimulatorCoordinatorPanel.test.tsx` (2 passed); `pnpm
  typecheck` (passed); `pnpm api:check` (passed); `pnpm lint` (passed).
- Known limitations: HTTP refresh can lag controller-only state changes by up to 500 ms; simulator
  mutations publish their returned shared-service state immediately. Firmware timing, UART, and
  NetworkManager behaviour remain intentionally outside this workstream.
- Specification drift: `None`.

## Independent review

- Reviewer: `Codex /root/ws2_review`
- Verdict: `Accepted`
- Required findings: `None`. The simulator composes the accepted shared services behind
  in-memory output and hotspot edges, serializes all controls, resets accessory state when the
  controller's simulation session changes, and publishes only `PanelService.display`. The
  coordinator preview accepts `CoordinatorStatus` and defaults to the live controller projection;
  React renders the returned display without owning transition or priority rules. The diff makes
  no coordinator-kernel changes, and the generated OpenAPI/client artifacts reproduce cleanly.
- Optional observations: `None`.
- Questions for orchestrator: `None`.

## Resolution

- Finding dispositions: No required findings; no remediation was needed.
- Simplification/deletion pass: Reread the simulator composition, routes, React integration, and
  focused tests as complete units. The final implementation retains one shared-service state
  owner, one simulation-only HTTP query, direct cause-oriented commands, and generated contracts;
  no component-local transition state, duplicate display priority, façade export, compatibility
  path, speculative simulator model, or obsolete test remains.
- Final verification: Final accepted-tree verification passed: `uv run pytest
  coordinator/tests/test_simulator_api.py coordinator/tests/test_deployment_profiles.py` (51
  passed); focused `uv run ruff check ...` (passed); `uv run mypy coordinator/src/e87canbus`
  (passed); `uv run lint-imports` (2 contracts kept); focused `pnpm test
  src/components/coordinator-panel/CoordinatorPanel.test.tsx
  src/components/simulator-workbench/SimulatorCoordinatorPanel.test.tsx` (2 passed); `pnpm
  typecheck`, `pnpm api:check`, and `pnpm lint` (passed). The first backend-suite attempt observed
  the existing timing-sensitive reset RGB assertion; an unchanged complete rerun passed, as did
  the same suite during implementation and review.

## Closure review

- Verdict: `Accepted`
- Remaining required findings: `None`. No remediation was required after the accepted independent
  review, the reviewed simulator implementation remains intact, and no release-blocking defect was
  introduced.
- Accepted commit: `TBD`
