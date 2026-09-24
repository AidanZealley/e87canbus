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

- Base commit: `f6dd22f5f56ee2fc76ce26919e8db5a0fd0c606b`
- Outcome: The kernel retains vehicle observations, desired state, profiles and complete projection changes. The bounded controller service owns the boot-scoped live revision and per-topic revisions. Simulation sends vehicle frames through in-memory CAN buses and the production kernel decoder without trace or project-device topology state.
- Files changed: Kernel inputs, commits and diagnostics; domain transition and button input values; controller loop and runtime contracts; live and simulated runtime composition, CAN bus and session; affected API command construction and focused tests; current simulation, reliability and live API documentation; ADR implementation notes.
- Decisions: Removed the kernel's duplicate revision and `state_changed` flag, unused input timestamps, the single-field `Transition` wrapper, the adapter snapshot wrapper, simulator trace events and buffer, and dead deadline mocks. Kept the simulation session ID as a direct service snapshot field because the simulated coordinator panel uses it to clear previews after reset. After review, added `ButtonPressed` to both runtime dispatch paths and removed consumerless frame outcome counters and simulator frame history. Kept periodic telemetry freshness, CAN reader faults, bounded ordered input and complete SSE topic replacements.
- Verification: The final targeted backend suite plus affected domain, bus, button, config and deployment tests passed (84). OpenAPI `--check`, mypy, ruff, lint-imports and `git diff --check` passed after remediation. Frontend `pnpm api:check` and `pnpm typecheck` passed. Frontend client and coordinator suites passed (20 and 36 tests). The console suite passed with one worker (97 tests).
- Known limitations or external checks: The default parallel `pnpm test` run timed out on one console route test; its full suite passed with one worker. No hardware or vehicle validation gate applies to this slice.
- Specification drift: None. The older live API document's statement about retaining an internal simulation trace was updated to match this slice's removal of consumerless trace state.

## Independent review

- Reviewer: Fresh independent Workstream 4 review agent.
- Verdict: Changes requested.
- Required findings:
  1. The ordered runtime path still rejects the retained button input. `CoordinatorKernel.dispatch` accepts `ButtonPressed` (`kernel/kernel.py:172-177`), but `LiveControllerRuntime.execute` rejects it because `CONTROLLER_INPUT_TYPES` omits it (`runners/live.py:49-60,216-225`), and `SimulatedControllerRuntime.execute` has no matching case (`runners/simulation/runtime.py:95-128`). Calling the simulated runtime with `ButtonPressed(0)` raises `TypeError: unsupported simulation command`. Slice 1.5 requires later device presses to enter the existing bounded owner; add the input to both runtime dispatch paths so Slice 02 can use that seam.
  2. Per-network frame outcome counters and the simulator's cumulative `_frame_history` have no retained product consumer. `kernel/health.py:27-35,78-100` stores received, decoded, ignored and malformed counts; `runners/simulation/runtime.py:67,147-169,191-197` carries them across resets. Repository search finds readers only in that history code and tests. The browser health projection in `api/models/coordinator_live.py:139-159` publishes reader faults but none of these counters, and current reliability documentation lists no counter contract. The packet requires deleting diagnostics with no retained consumer. Remove these counters and history while preserving reader faults, inbox overflow and their health publication.
- Optional observations: `kernel/commit.py:3-5,45-50` says every commit follows a mutation, although no-op intents and periodic freshness ticks can return commits with no changed topic. Align that comment with the contract when touching the file.
- Questions: None.

Review evidence: The focused architecture, controller loop, live and simulated runtime, simulator API, live projection, SSE and application-controller suite passed (49 tests). `uv run lint-imports` and `git diff --check` passed. The bounded queue, ingress timestamps and network identity survive in `service/loop.py:292-315`, `runners/live.py:77-129` and `kernel/kernel.py:187-204`. Desired steering state and active profile/curve activation still commit complete snapshots with fixed changed topics. The service owns the boot-scoped revision and per-topic revisions (`service/loop.py:445-475`), and browser SSE sends complete topic replacements. Active-code search found no old device role, effect executor, output seam, exact deadline scheduler, device or lighting topic, simulator peer topology or trace buffer. Live and simulated runtimes remain separate.

## Resolution

- Finding dispositions: Accepted both Required findings. Both runtimes now pass `ButtonPressed` to the kernel through their ordered execution paths. Removed the frame outcome counters and reset history because no product projection reads them. Also accepted the Optional `Commit` docstring correction.
- Simplification/deletion pass: Removed the counter state and its test-only reset logic outright. Retained CAN reader faults, inbox overflow health, ingress timestamps and network identity. The implementation also removed duplicate revisions, unused wrappers, trace and topology state without adding a replacement output seam.
- Final verification: The final targeted backend suite passed (84 tests). OpenAPI `--check`, mypy, ruff, lint-imports and `git diff --check` passed after remediation. Frontend API and type checks passed in the initial implementation, and its client, coordinator and serial console suites passed.

## Closure review

- Verdict: Approved. Both accepted Required findings are resolved in the cumulative diff from `f6dd22f`.
- Remaining required findings: None. Both runtimes now accept `ButtonPressed` and dispatch it to the kernel; the focused runtime test confirms that an assigned press changes desired steering state and reports `StateTopic.STEERING` in live and simulated execution. The service still serializes submitted work through its bounded inbox and records changed topics with its boot-scoped revision. The kernel and simulator no longer retain frame outcome counters or reset history; network reader faults and inbox overflow still feed the published health projection. The focused architecture, controller loop, runtime, simulation, SSE publication and button profile suite passed (31 tests), and `git diff --check` passed.
