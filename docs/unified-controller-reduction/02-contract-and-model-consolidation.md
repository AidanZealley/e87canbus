# Phase 2: Contract and model consolidation

## Goal

Remove parallel representations of the same live, command, resource and diagnostic facts. Keep one
canonical typed value per fact and adapt it only at a real framework or wire boundary.

Minimum production reduction: **200 lines**.

This phase must preserve every public HTTP and Socket.IO payload unless Phase 1 proves there is no
consumer and explicitly approves removal.

## Preconditions

- Phase 1 is `Verified` with an approved contract/model deletion ledger.
- Public payload snapshots and generated-contract checks are green at the phase base.
- Every model proposed for deletion has a consumer search and replacement path.

## Reduction priorities

Inspect and simplify:

- `api/models/live.py` conversions that manually rebuild already-typed projections.
- Backend domain/service/API types with identical fields and lifetime.
- Frontend HTTP-owned types reused to describe Socket.IO-owned state, or vice versa.
- Repeated steering-curve, device, network, health and envelope shapes.
- Dictionary serializers that duplicate Pydantic/dataclass serialization without policy.
- Response wrappers whose only purpose is forwarding another immutable result.
- Generated schema definitions that balloon solely because equivalent named definitions are emitted
  repeatedly; fix the generator rather than hand-editing output if reduction is safe.

Prefer:

- A canonical domain/service projection with one boundary adapter.
- Named generated definitions reused by reference where tooling supports it.
- Type aliases derived from an owning contract instead of copied structural declarations.
- Direct Pydantic validation/serialization at the API edge.

Avoid:

- A new “shared models” package that merely relocates duplication.
- Exposing FastAPI/Pydantic objects inside the controller core.
- `Any`, unchecked mapping access or casts used to erase an adapter.
- Changing wire field names to save internal code.

## Required behavior

- Protocol version, `boot_id`, revision and topic semantics remain unchanged.
- Reconnect snapshots remain complete and authoritative.
- HTTP acknowledgement/resource error shapes remain exact.
- Durable and live ownership remain separate.
- Unknown protocol versions and malformed boundary data still fail visibly.

## Tests

- Retain public payload/schema tests and frontend contract consumption tests.
- Replace private serializer tests with public payload assertions when the serializer disappears.
- Add no mirror tests for a new intermediate representation.
- Run dead-symbol searches for every removed model and serializer.

## Verification

```text
uv run pytest -q
uv run ruff check .
uv run mypy coordinator/src/e87canbus
uv run python scripts/generate_live_contract.py --check
uv run python scripts/generate_custom_protocol.py --check

pnpm test
pnpm lint
pnpm typecheck
pnpm build

git diff --check
```

## Completion criteria

- At least 200 net production lines are removed, or a larger approved cross-phase deletion is
  completed and recorded.
- At least one independently maintained contract copy or boundary representation is gone.
- The normal publication and command flows cross fewer named transformations.
- No public payload or ownership boundary changes accidentally.
- No type safety, validation or generated-contract check is weakened.
- All removed types/serializers have no remaining import, test or active-document references.

