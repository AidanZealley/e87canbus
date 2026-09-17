# Workstream 6: final transport cleanup

Status: accepted.

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

- Base commit: `75e715a8678f9af619e268a7ecf64df47d77434c`
- Outcome: Removed the final shared Socket.IO and Engine.IO adapter, tests, dependencies, lock
  entries, SPA exclusions, dead configuration, script aliases and current documentation claims.
  Both browser contracts now generate and drift-check through the two root API commands only.
- Files changed: Deleted the bounded Socket.IO adapter and its tests; reduced host configuration,
  SPA routing and affected tests; removed Python and frontend dependencies and lock entries;
  flattened the frontend API scripts; updated root, frontend, host, protocol, simulation,
  reliability, network, provisioning and deployment documentation. Added the console generated
  client to the existing generated-code lint exclusions and made four accepted empty-stream test
  helpers lint-clean without changing their behavior. Formatted `e87ctl/src/e87ctl/cli.py` to clear
  two inherited Ruff violations required by the packet's broad command.
- Decisions: Kept only SSE-used publication rates, subscriber capacity and shutdown timeout.
  Removed the old `http:*` and `console-api:*` command aliases instead of forwarding them.
  Preserved backend CAN trace, device registry, simulation protocol-version controls and generated
  custom protocol. Preserved the historical Socket.IO ADR and approved migration source text.
- Verification: `pnpm api:generate` regenerated both OpenAPI documents and both Hey API clients,
  then `pnpm api:check` passed without changing tracked output. The custom protocol check passed;
  backend tests passed 960 tests; mypy passed 142 source files; Ruff, both import contracts and
  `git diff --check` passed. Frontend typecheck and lint passed; tests passed 8 files/18 tests for
  coordinator-client, 25 files/102 tests for console and 11 files/38 tests for coordinator; both
  application builds passed with the existing coordinator chunk-size warning. Precise repository
  searches found no runtime, build, manifest, lock, alias or current-document reference to the
  retired transports or browser protocol names.
- Known limitations or external checks: The workflow's final local browser validation gate remains
  pending. Search matches intentionally remain in ADR 0008, the approved migration requirements,
  ignored local package-store artifacts, backend controller snapshot method names and the retained
  custom-CAN protocol-version implementation and tests.
- Specification drift: None. The only inherited correction outside the cleanup files was
  formatting-only: Ruff initially reported unsorted imports at `e87ctl/src/e87ctl/cli.py:1` and an
  overlong line at `e87ctl/src/e87ctl/cli.py:84`; import ordering and line wrapping now pass without
  behavior changes.

## Independent review

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Verdict: Approve with required changes. Source, dependency, lock, configuration, generation and
  documentation cleanup passed, but one deployment remnant remains.
- Required findings: Remove nginx's Engine.IO-era WebSocket upgrade map and the `Upgrade` and
  `Connection` proxy headers from the ordinary HTTP location. Nothing serves WebSockets now, and
  the map forces `Connection: close` for normal upstream requests.
- Optional observations: Replace a stale `live-events contract` source comment; make the root README
  Ruff command match CI by including `e87ctl`; keep the existing list punctuation; comments on
  lint-only empty async generators are unnecessary; slow-disconnect counters belong to their
  accepted publisher owners.
- Questions for orchestrator: Preserve accepted ADR 0008 as historical evidence; the approved v2
  specifications supersede it for current behavior. Let removed `/ws` paths fall through to the SPA
  like any other unknown client route now that no server owns that prefix.

## Resolution

- Finding dispositions: Accepted the nginx finding as Required because the packet explicitly owns
  deployment remnants and the headers affect ordinary HTTP keepalive. Promoted the stale source
  comment and README Ruff command to the same cleanup batch. Rejected new explanatory lint comments
  and changes to accepted publisher diagnostics. Historical ADR 0008 remains untouched.
- Simplification/deletion pass: Removed the unused nginx WebSocket upgrade map and both upgrade
  proxy headers instead of replacing them with SSE-specific compatibility settings. Added focused
  negative assertions to the existing coordinator SSE deployment test. Updated the button-pad
  packing comment to name the coordinator projection and made the root Ruff command match CI and
  this packet. ADR 0008, accepted SSE code, publisher diagnostics, list punctuation and the
  lint-only generator helpers remain unchanged.
- Final verification: Focused deployment tests passed 50 tests, and focused searches found the
  removed nginx directives only in their negative assertions. Every packet command passed: the
  custom protocol check; 960 backend tests; mypy over 142 source files; Ruff; both import contracts;
  `git diff --check`; frontend API drift check, typecheck and lint; 8 files/18 coordinator-client
  tests, 25 files/102 console tests and 11 files/38 coordinator tests; and both application builds.
  The coordinator build retains its existing chunk-size warning.

## Closure review

- Verdict: Accepted. The focused reviewer confirmed the Engine.IO-era nginx map and upgrade headers
  are absent, the SSE location retains its required streaming settings, current source/docs no
  longer cite the retired contract, and the documented Ruff command matches CI.
- Remaining required findings: None.
- Accepted commit: `5badf6da8df06a61b9f69dd38a48aee5ca2c8e70`
