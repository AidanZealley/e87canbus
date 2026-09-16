# Workstream 1: retire legacy live UI

Status: implementing.

## Task packet

### Outcome

Neither frontend consumes browser trace data or the live device-registry projection. The driving
console has no connected-device panel. The coordinator workbench has no trace, network-topology or
custom-CAN device controls. Remaining simulator vehicle and coordinator-panel controls still work
over the existing transport.

### Scope

- Delete the coordinator trace view, trace table, filters, detail UI, trace store and subscription
  lifecycle.
- Delete the driving-console device panel and status tiles.
- Delete the coordinator workbench's legacy button-pad and Servotronic device cards, custom protocol
  controls and network topology.
- Remove frontend selectors, fixtures and tests that exist only for trace or registry UI.
- Adapt remaining steering availability and health presentation to use the approved steering and
  health projections instead of registry connection state.
- Reduce the current coordinator live store and Socket.IO listener set so no frontend code consumes
  `devices.state` or `trace.batch`. The old generated contract and backend events remain temporarily.
- Update user-facing simulator documentation that would otherwise direct someone to removed UI.

### Non-goals

- Do not add SSE, change server publication or edit OpenAPI generation.
- Do not remove the backend simulation trace, simulated peers, CAN registry, custom protocol or
  ISO-TP behavior used by tests and later migration slices.
- Do not replace removed UI with HTTP polling, another projection or a compatibility component.
- Do not remove Socket.IO dependencies or generated live schemas in this workstream.

### Initial ownership

This agent owns the affected files in:

- `frontend/apps/coordinator/src/components/simulator-workbench/`;
- `frontend/apps/console/src/components/car-settings/` and other direct registry consumers;
- `frontend/packages/coordinator-client/src/live/` for trace and registry consumer removal;
- focused frontend tests and fixtures for those paths; and
- directly affected simulator sections of `README.md`, `frontend/README.md` and
  `docs/simulation.md`.

The agent may update another frontend component only when a removed registry selector is its direct
input. It must not edit backend simulation code or generated contracts.

### Required seams

- Remaining components may use vehicle, engine, steering, buttons, lighting and health projections.
  No component may use the live device registry as a proxy for capability or health.
- The current Socket.IO connection remains the authority until Workstream 3.
- Internal trace and simulated-device behavior remain available to Python tests even though no
  browser exposes them.

### Acceptance criteria

- Searches find no frontend trace subscription, trace store, trace view or live device-registry
  selector.
- The driving-console settings routes contain no connected-device section.
- The workbench contains no custom-CAN device card, protocol-version control, network topology or
  CAN trace.
- Remaining vehicle controls, coordinator-panel controls, steering displays and button-profile
  editing render and behave under the current live transport.
- Frontend packages build without weakening generated types or adding replacement mock state.
- Backend simulation and protocol tests are unchanged except for documentation or test names that
  directly referred to the removed browser UI.

### Targeted verification

Run from `frontend/`:

```text
pnpm --filter @e87canbus/coordinator-client test
pnpm --filter @e87canbus/coordinator-client typecheck
pnpm --filter @e87canbus/coordinator test
pnpm --filter @e87canbus/coordinator typecheck
pnpm --filter @e87canbus/coordinator build
pnpm --filter @e87canbus/console test
pnpm --filter @e87canbus/console typecheck
pnpm --filter @e87canbus/console build
```

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_simulation_runtime.py hosts/tests/test_simulation_bus.py hosts/tests/test_generated_protocol.py
git diff --check
```

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 1 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/01-retire-legacy-live-ui.md and every source-of-truth document it links. Inspect the uncommitted diff and surrounding frontend consumers, tests and documentation. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check that trace and registry UI are fully removed, remaining operational UI no longer infers capability from registry state, backend simulation remains intact and no replacement projection or polling mechanism was introduced." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 1 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/01-retire-legacy-live-ui.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
```

## Implementation handoff

- Base commit: `ee27897ebb6e9f17fba97ce232edbc68b51d3aaa`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (Claude command used, or the recorded fresh-session fallback)
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
