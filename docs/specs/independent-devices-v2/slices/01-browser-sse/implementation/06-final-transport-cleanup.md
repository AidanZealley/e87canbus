# Workstream 6: final transport cleanup

Status: not started.

## Task packet

### Outcome

The repository contains only the two generated Hey API SSE paths. Socket.IO, Engine.IO and the
bespoke live-contract pipeline have no source, dependency, configuration, diagnostic, test or
current documentation footprint. Internal CAN simulation and protocol machinery remain.

### Scope

- Search the full repository for remaining Socket.IO, Engine.IO, old live schemas, old generated
  mappings, protocol-version envelopes, resync events, trace subscriptions and live registry
  consumers.
- Delete the shared bounded Socket.IO adapter, authorization remnants, SPA exclusions, tests and
  lifecycle hooks with no remaining consumer.
- Remove `python-socketio`, `socket.io-client`, `json-schema-to-typescript` and their lockfile entries
  when searches prove they are unused.
- Remove obsolete live-publication configuration and diagnostics. Keep bounds and diagnostics that
  directly describe the SSE publishers.
- Simplify contract generation and watch scripts around the coordinator and console OpenAPI
  documents. Remove old command aliases rather than forwarding them.
- Update root, host, frontend, protocol, simulation, reliability and deployment documentation to
  describe the implemented SSE paths and reduced UI.
- Run a deletion pass for temporary migration seams introduced by Workstreams 2 and 4.

### Non-goals

- Do not change accepted event contracts, browser state ownership or reconnect behavior.
- Do not remove backend simulation trace, CAN device registry, ISO-TP or generated custom CAN
  protocol merely because their browser projections are gone.
- Do not reorganize unrelated packages or documentation.
- Do not add abstractions, flags or aliases for the removed transport.

### Initial ownership

This agent owns:

- shared transport adapters and tests with no accepted consumer;
- root and frontend dependency manifests and lockfiles;
- shared contract generation and watch scripts;
- obsolete configuration and publisher diagnostic fields;
- SPA, proxy and deployment remnants of Socket.IO; and
- directly affected current documentation across the repository.

Behavioral defects in accepted coordinator or console SSE seams return to their original owner.

### Required seams

- `pnpm api:generate` and `pnpm api:check` cover both OpenAPI documents and both generated clients.
- Current documentation gives the standard three-command local startup and distinct stream origins.
- Searches distinguish current code from historical ADR text and backend custom-CAN protocol
  version fields. Do not delete historical evidence or unrelated wire protocol behavior.

### Acceptance criteria

- No runtime or build dependency on Socket.IO or Engine.IO remains in manifests or locks.
- No source imports, mounts, proxy rules, authorization tables or tests refer to either transport.
- No bespoke live JSON Schema, generator, generated event map, protocol-version envelope or resync
  path remains.
- Live configuration and health expose only values used by the SSE implementation or operators.
- Both OpenAPI generation paths have non-mutating drift checks used by CI.
- Current documentation matches the two SSE streams, generated-client boundary, reduced Zustand
  role and removed simulator UI.
- Internal CAN trace and project-device protocol tests still pass.

### Targeted verification

Run from the repository root:

```text
uv run python scripts/generate_custom_protocol.py --check
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Use `rg` to audit retired names across source, manifests, locks and current documentation. Record any
intentional match, such as a historical ADR or the unrelated custom CAN protocol version, in the
handoff instead of weakening the search.

## Review commands

Independent review:

```text
claude -p "Act as the independent reviewer for Workstream 6 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/06-final-transport-cleanup.md and all accepted dependency handoffs. Inspect the uncommitted diff and search the full repository. Run proportionate read-only checks. Do not edit files. Return a verdict followed by evidence-backed Required, Optional and Question findings. Check dependency and lock removal, dead adapters and configuration, contract generation, CI drift checks, current documentation and accidental deletion of backend CAN simulation or custom protocol coverage. Reject compatibility aliases and speculative shared streaming machinery." --model opus --effort medium --permission-mode plan
```

Closure review:

```text
claude -p "Perform the focused closure review for Workstream 6 of the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/06-final-transport-cleanup.md, including its recorded Independent review and Resolution, then inspect the current uncommitted cumulative diff. Verify each accepted Required finding and check its fix for release-blocking defects. Do not reopen optional suggestions or conduct another broad review. Do not edit files. Return a closure verdict and any remaining Required findings with evidence." --model opus --effort medium --permission-mode plan
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
