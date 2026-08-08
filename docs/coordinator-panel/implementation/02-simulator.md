# Workstream 2: simulator integration

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- API/publication choice: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations: `TBD`
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
