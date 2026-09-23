# Workstream 4: Reduce the coordinator to its retained responsibilities

Status: not started.

## Task packet

### Outcome

The surviving kernel, controller loop, runtimes, diagnostics and live projections contain only the
four responsibilities approved by Slice 1.5.

### Scope

- Audit every kernel input, state field, timer, commit value and diagnostic against the Slice 1.5
  responsibility test. Delete values with no retained consumer.
- Remove exact deadline methods and arbitration if periodic telemetry freshness is the only
  remaining clock-driven behavior.
- Remove `StateTopic.DEVICES`, `StateTopic.LIGHTING`, consumerless adapter projections and device or
  actuator health.
- Consolidate duplicate kernel/service revision and `state_changed` bookkeeping where current
  browser publication does not require both. Keep the boot-scoped revision and per-topic revisions
  used by SSE.
- Narrow `ControllerRuntime` and its live and simulated implementations to retained input,
  lifecycle, periodic telemetry and projection behavior.
- Simplify the simulator around vehicle input. Delete fixed-point peer draining, topology state and
  trace plumbing that has no retained consumer.
- Remove facade exports, fixtures, mocks and tests coupled only to the former architecture.
- Update ADR implementation notes and current documentation to match the final code.

### Non-goals

- Replacing the single-owner thread or bounded inbox with asyncio.
- Merging live and simulated runtime classes merely to reduce class count.
- Moving SQLite or device API concerns into the kernel.
- Adding the independent scene, device API, vehicle actuation or generic event infrastructure.

### Initial ownership

- `hosts/src/e87canbus/kernel/`
- `hosts/src/e87canbus/service/loop.py` and surviving diagnostics
- live and simulated runtime contracts and composition
- browser live projection and publication code affected by removed topics
- architecture tests, focused runtime/publication tests and current documentation

Integration exception: simplify domain snapshot helpers when a removed runtime or commit value is
their only consumer. Preserve API behavior that Slice 1.5 explicitly retains.

### Required seams

- CAN readers, HTTP commands and later device presses still enter one bounded ordered owner.
- Vehicle frames retain ingress time and network identity until the kernel decodes them.
- Desired state changes produce complete immutable snapshots and accurate changed topics.
- Browser SSE keeps its boot-scoped revision and complete replacement semantics.
- The controller loop has no device transport or actuator knowledge.
- Each retained abstraction has at least two real responsibilities or enforces an approved boundary;
  otherwise prefer a direct call or value.

### Acceptance criteria

- Every retained kernel concern maps to vehicle observation, desired intents, profiles/curves or
  complete publication projections.
- The controller loop remains bounded and single-owner without exact deadline machinery that has no
  consumer.
- There is one externally meaningful live revision source and no ceremonial state-change flag.
- Live and simulated runtimes contain no device peer, effect executor or unused output seam.
- Vehicle telemetry, steering/profile operations, health reporting and browser SSE pass meaningful
  tests.
- Architecture and import checks show no dependency from kernel/domain code into adapters.
- A deletion pass finds no compatibility facade, empty protocol or speculative configuration point.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_architecture.py hosts/tests/test_controller_loop.py hosts/tests/test_runtime.py hosts/tests/test_simulation_runtime.py hosts/tests/test_simulator_api.py hosts/tests/test_live.py hosts/tests/test_live_publication.py hosts/tests/test_application_controller.py
uv run python scripts/generate_openapi.py --check
uv run mypy
uv run ruff check hosts scripts/generate_openapi.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm typecheck
pnpm test
```

A deleted test file is not a failed check when it covered only removed behavior. Record that deletion
and run the surviving tests for each retained behavior named in the acceptance criteria.

## Review briefs

Independent review:

```text
Act as the independent reviewer for Workstream 4 of the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/04-simplify-coordinator-core.md, all accepted handoffs, Slice 1.5, ADRs 0001, 0003, 0008, 0017 and 0018. Inspect the cumulative code around the kernel, commit contract, controller loop, runtimes, diagnostics, simulation and browser publication. Run proportionate read-only checks. Write findings only in this packet's Independent review section. Return a verdict followed by evidence-backed Required, Optional and Question findings. Trace each retained concern to the four approved responsibilities. Check ordered ownership, timestamps, bounded inbox, desired state, profiles and curves, vehicle decoding, changed topics and SSE revisions. Confirm no old device role, transport, output or simulation type survived Workstream 3. Reject dead abstractions, duplicate authority, unnecessary deadlines, merged runtimes without benefit and speculative output machinery.
```

Closure review:

```text
Perform the focused closure review for Workstream 4 of the simplified coordinator workflow. Read its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify every accepted Required finding and check its fix for release-blocking ownership, ordering, publication, lifecycle or simplification defects. Do not reopen optional suggestions or conduct another broad review. Write the verdict only in this packet's Closure review section. Return a closure verdict and any remaining Required findings with evidence.
```

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD` (fresh lead subagent)
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
