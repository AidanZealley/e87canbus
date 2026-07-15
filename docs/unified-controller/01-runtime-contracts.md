# Phase 1: Runtime contracts and regression baseline

## Goal

Turn the approved architecture into explicit framework-independent contracts and an accepted ADR
before changing process composition or public transports. Preserve all current behavior while
establishing the vocabulary and tests later phases share.

This phase does not add Socket.IO, change HTTP/WebSocket payloads, combine entry points, enable live
transmission or refactor working modules merely to match a proposed directory tree.

## Dependencies and files to inspect

Before designing changes, inspect completely:

- `coordinator/src/e87canbus/runtime.py`, `live.py`, `output.py` and `config.py`.
- `coordinator/src/e87canbus/application/` and `protocol/`.
- `coordinator/src/e87canbus/api/` and `simulation/` ownership/lifecycle code.
- Existing coordinator tests around kernel order, queue overflow, simulation and publication.
- ADRs 0001-0007 and the hardware evidence checklists referenced by ADR 0006.
- Current frontend snapshot/socket/query types so compatibility is described accurately.

## Architecture decision record

Add one accepted ADR recording the approved unified-controller decision. It should:

- Preserve ADRs 0001-0006 rather than restating or silently superseding their safety boundaries.
- State that the live and simulated compositions converge into one modular process and lifecycle.
- State that physical/simulated behavior is selected through adapters.
- Assign HTTP to commands/resources and Socket.IO to live-state replication.
- Assign Zustand to frontend live state and TanStack Query to HTTP server state.
- Require reconnect snapshots, bounded publication and single ingress authority per device.
- Keep ADR 0007 Proposed and explicitly outside the implementation authority of this roadmap.
- Record rejected generic brokers, event sourcing, separate simulator state and full-car simulation.

Update `docs/decisions/README.md` without rewriting historical ADR status.

## Runtime vocabulary

Define or consolidate small immutable values for the following concepts. Reuse current values where
they already express the contract clearly.

### Ingress

`ControllerInput` remains a closed union. Every time-sensitive input contains its ingress or
decision timestamp. At minimum it covers:

- Startup and shutdown.
- Routed CAN frames.
- Controller timer evaluation.
- Runtime configuration/profile activation.
- Semantic operational commands needed by current features.
- Reader, inbox, effect and actuator failures.

Do not put FastAPI request objects, Socket.IO session IDs or simulator UI models in this union.

### Commit

Define the final intended commit semantics:

```text
Commit
  revision             monotonic within one controller boot
  snapshot             complete immutable application projection
  effects              ordered desired external actions
  changed_topics       closed set derived from projection differences
  state_changed        compatibility/convenience value if still useful
```

The controller mutates state before returning a commit. Effect success is not implied by the
commit; output failure returns as a later input and updates health.

### Runtime identity

Specify:

- A new opaque `boot_id` for every controller-service start.
- Kernel/controller revision monotonicity within that boot.
- A separate simulation session identity only if reset semantics still require it.
- A bounded trace sequence scoped by its owning session/boot.

Use monotonic time for freshness and latency decisions. Use canonical UTC only for external
timestamps and durable records.

### Changed state topics

Define a closed internal state-topic enum sufficient for current controller projections:

```text
vehicle
engine
steering
buttons
devices
health
```

This is a commit projection hint, not a generic pub/sub framework. Topic values must not acquire
arbitrary runtime registration or string-based domain dispatch. Durable resource changes originate
from repository/application services and trace batches originate from bounded diagnostics; neither
is fabricated as a controller-state change merely to share the Socket.IO transport.

## Public envelope specification

Document, but do not necessarily expose yet, one versioned live message envelope:

```json
{
  "protocol_version": 1,
  "boot_id": "opaque",
  "revision": 42,
  "emitted_at": "canonical UTC timestamp",
  "data": {}
}
```

Specify that:

- Revisions are compared within a matching `boot_id`.
- Topic consumers retain their last applied revision independently.
- A `boot_id` change invalidates all previous live revisions.
- Payload models are complete for their topic rather than JSON patches.
- Unknown protocol versions fail visibly rather than being guessed.

Do not create a second handwritten domain model solely for this envelope. Pydantic models may adapt
framework-independent snapshot values at the API boundary.

## Regression characterization

Add focused tests only where existing behavior is insufficiently pinned for safe migration:

- Kernel input order and revision behavior.
- Startup and shutdown effects.
- CAN receive timestamp preservation.
- Effect failure feedback without recursive transition.
- Queue overflow/fatal health behavior.
- Current simulator frames traversing protocol decode and kernel commit.
- Complete button LED snapshot behavior.
- Current initial/reconnect snapshot and trace identity behavior.
- Current settings/profile transaction and invalidation behavior.

Tests should characterize intended behavior, not freeze accidental class names or private call
graphs.

## Documentation

- Add the accepted ADR and index entry.
- Update module documentation only where ownership is currently ambiguous.
- Record any existing behavior that conflicts with the approved contract; do not silently change it
  in this phase.

## Verification

Run focused runtime/application/simulation/API tests plus:

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_custom_protocol.py --check
pnpm test
pnpm lint
pnpm typecheck
pnpm build
git diff --check
```

No browser or physical test is required because public behavior should not change.

## Completion criteria

- The unified architecture is recorded in an accepted ADR consistent with ADRs 0001-0006.
- Runtime input, commit, boot/revision, topic and envelope semantics are unambiguous.
- Existing safety and simulation-path behavior needed by migration has regression coverage.
- No public HTTP/WebSocket behavior or dependency changes occur unintentionally.
- No live transmitter or physical steering capability is added.
- Conflicts between the approved design and current implementation are recorded for the phase that
  owns their resolution.
