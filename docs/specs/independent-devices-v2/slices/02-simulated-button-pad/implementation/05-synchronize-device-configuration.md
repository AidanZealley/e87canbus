# Workstream 5: Synchronize durable device configuration

Status: not started.

## Task packet

### Outcome

One lifecycle-owned service turns current button state into durable per-device envelopes and exposes
a bounded stream of complete replacements for a later HTTP route. It never blocks the controller
thread and never invents generation state outside SQLite.

### Scope

- Add one direct button-pad configuration service using Workstream 1's scene and Workstream 3's
  repository.
- On first contact, atomically get or create the authenticated button pad's envelope from the current
  role-default scene.
- Consume controller `BUTTONS` notifications, compare the feedback-free complete scene with all
  stored button-pad documents, persist changed generations, and publish replacements immediately.
- Fan out the existing single controller notification directly to the browser publisher and this
  service. Do not change `ControllerLoop` into a general event bus.
- Expose an async iterator or equally direct subscription seam whose first value is the current
  durable envelope and whose later values are complete replacements.
- Give each subscriber bounded pending output and disconnect saturation or failure without blocking
  the controller or other subscribers.
- Integrate service start and stop into FastAPI lifespan with deterministic ordering.

### Non-goals

- An HTTP route, authorization-table change, SSE framing, nginx or generated OpenAPI artifacts.
- Replay, event IDs, per-topic streams, presence, status expiry or a generic event/publisher framework.
- Servotronic configuration or a cache of authoritative documents.

### Initial ownership

- a direct device configuration service under `hosts/src/e87canbus/api/internal/`
- `hosts/src/e87canbus/api/main.py` and `api/internal/lifecycle.py`
- focused synchronization, concurrency and lifecycle tests under `hosts/tests/`

Integration exception: make the smallest direct adjustment to the existing controller notification
composition. Do not alter routes, nginx, generated artifacts or simulation devices.

### Required seams

- Runtime notification performs no SQLite work and awaits no subscriber. It offers only the latest
  relevant immutable snapshot into event-loop-owned work.
- New-device creation and subscription registration are ordered against replacement publication so
  no older scene can follow the initial envelope and no current change can be missed.
- The repository decides whether a document changed and owns generation advancement. The service
  keeps no second generation counter or authoritative document cache.
- One pending complete envelope per subscriber is sufficient. On another change before delivery,
  either safely replace the pending value or disconnect; never grow an unbounded queue.
- Lifecycle shutdown releases subscribers and background tasks within the existing configured bound.

### Acceptance criteria

- First contact returns exactly one complete current durable envelope.
- Repeated contact and service restart return the stored envelope without incrementing generation.
- A profile or application-state change that alters the feedback-free scene persists and publishes
  one next generation; irrelevant and identical changes do neither.
- Multiple stored button pads receive their own envelopes with independent generations from the one
  current role-default scene.
- Active-only animation and assigned state remain correct on initial and replacement values.
- A slow subscriber cannot block controller work, other subscribers or shutdown and cannot grow
  memory without a bound.

### Targeted verification

Run from the repository root:

```text
uv run pytest -q hosts/tests/test_device_configuration_service.py hosts/tests/test_device_state_repository.py hosts/tests/test_button_profile_api.py hosts/tests/test_controller_loop.py
uv run mypy
uv run ruff check hosts
uv run lint-imports
git diff --check
```

The implementation agent creates `hosts/tests/test_device_configuration_service.py` if it does not
yet exist.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 5 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/05-synchronize-device-configuration.md, all accepted dependency handoffs, ADR 0017 and the linked product documents. Inspect the uncommitted diff and surrounding controller notification, kernel snapshot, SQLite repository, configuration service and FastAPI lifespan. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check first-contact ordering under concurrent changes, durable compare-and-increment semantics, restart behavior, feedback-free scene publication, multiple independent device generations, nonblocking bounded subscribers and shutdown. Reject a second generation source, event log, cache, generic event bus or generic SSE machinery." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 5 of the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/05-synchronize-device-configuration.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking ordering, durability, lifecycle or bounded-subscriber defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
