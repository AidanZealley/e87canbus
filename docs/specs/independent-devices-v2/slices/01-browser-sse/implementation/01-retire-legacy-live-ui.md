# Workstream 1: retire legacy live UI

Status: accepted; implementation commit pending.

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
- Outcome: Removed browser trace and device-registry consumption, the console device settings tab,
  and the workbench's custom-CAN device, topology and trace UI. Retained coordinator-panel,
  simulated-vehicle and button-profile controls.
- Files changed: Deleted the trace store and legacy coordinator/console UI trees; reduced the live
  store, transport listeners and affected tests; updated steering and button-profile consumers,
  frontend dependencies, lockfile, and simulator documentation.
- Decisions: Steering controls and button presentation now use synchronization, steering state,
  curve capability and health faults. Missing Servotronic telemetry affects telemetry presentation
  without using registry presence as a capability gate. The generated contract and backend events
  remain unchanged for later workstreams.
- Verification: All packet commands passed. Coordinator-client: 6 files/16 tests; coordinator: 16
  files/62 tests; console: 23 files/98 tests; backend selection: 50 tests. All three typechecks and
  both application builds passed. `git diff --check` passed. One concurrent console-suite attempt
  timed out under competing Vitest runs; its isolated rerun passed.
- Known limitations or external checks: No manual browser session was run; the workflow's final
  local browser validation gate remains pending.
- Specification drift: None.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: Changes requested. All packet checks passed and the removals were complete, but two
  product-facing issues block acceptance.
- Required findings: The console enabled Servotronic mode controls and previews whenever live state
  was synchronized even though the backend still rejects those commands without a usable
  controller. Derive the conservative gate from the approved steering projection and health state.
  The coordinator steering-curve editor became orphaned when its last workbench host was deleted;
  remove the dead component tree.
- Optional observations: Run the formatter on changed files; retain exhaustive listener typing;
  remove the unused transport return value and handle; derive topic names from the generated event
  map; avoid low-value mocked negative assertions; clean-checkout removes empty directories.
- Questions for orchestrator: The legacy coordinator-panel HTTP poll is pre-existing and belongs to
  later transport cleanup if it remains after cutover. The coordinator workbench need not retain a
  steering display because the approved scope explicitly removes its legacy Servotronic card; the
  driving-console steering display remains.

## Resolution

- Finding dispositions: Accepted both Required findings. Use `steering.servotronic !== null` as the
  conservative projection-owned availability signal, alongside existing health gates; do not add a
  contract field in this workstream. Promoted the stale root README simulator claim to required
  documentation cleanup. Accepted the formatter and small transport/type simplifications where
  they reduce code without changing behavior. Deferred the mocked-test observation unless the
  affected test can be made meaningful without rebuilding deleted coverage.
- Simplification/deletion pass: Deleted the orphaned coordinator steering editor, chart wrapper,
  trace-only UI wrappers and coordinator `recharts` dependency. The live store now derives retained
  topics from generated types, the transport listener map is exhaustive for retained events, and
  startup keeps only a boolean guard. Prettier formatted every changed TypeScript file.
- Final verification: Coordinator-client 6 files/16 tests, coordinator 11 files/38 tests, console 23
  files/100 tests, and the 50 selected backend tests passed. All three typechecks, both application
  builds, stale-reference searches and `git diff --check` passed. After the closure correction,
  full frontend lint, coordinator-client tests/typecheck and `git diff --check` passed.

## Closure review

- Verdict: Accepted after one narrow closure correction. The reviewer confirmed both original
  Required findings and the promoted documentation fix. The orchestrator accepted the explicit
  retained-topic mapping after lint and focused client checks passed.
- Remaining required findings: None.
- Accepted commit: `TBD`
