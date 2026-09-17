# Browser SSE whole-feature review

Status: initial whole-feature review in progress.

## Reviewer task packet

Review the full branch against the starting commit recorded in [plan.md](plan.md) and the approved
Slice 01 sources. Read accepted handoffs, but independently inspect the combined diff and surrounding
code.

Audit specification completeness, both host lifecycles, initial snapshot ordering, bounded clients,
reconnection, origin routing, generated OpenAPI and Zod seams, authorization, deployment proxying,
dependency direction, deleted simulator UI, stale mocks, meaningful tests and documentation. Search
for remaining Socket.IO, Engine.IO, bespoke live-contract, protocol-version, resync, browser trace
and live device-registry consumers. Distinguish intentional historical text and backend CAN protocol
coverage from live transport leftovers.

Confirm that the result uses two direct host-specific implementations where their contracts differ.
Reject a generic stream framework, compatibility layer or configuration point without an approved
requirement.

## Review commands

Initial whole-feature review:

```text
claude -p "Act as the whole-feature reviewer for the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/README.md, plan.md, all six accepted workstream records, docs/specs/independent-devices-v2/slices/01-browser-sse.md, architecture-and-boundaries.md and live-and-device-api.md. Review the complete branch diff against the starting commit recorded in the plan and inspect surrounding code. Run proportionate read-only checks. Do not edit files. Audit specification completeness, cross-host seams, lifecycle, authorization, generated OpenAPI and Zod validation, all reconnect modes, bounded subscriber behavior, distinct origins, Zustand scope, dependency removal, stale simulator UI and documentation agreement. Return a verdict followed by evidence-backed Required findings grouped by original workstream owner, Optional observations and Questions." --model opus --effort medium --permission-mode plan
```

Focused closure review:

```text
claude -p "Perform the focused whole-feature closure review for the browser SSE workflow. Read docs/specs/independent-devices-v2/slices/01-browser-sse/implementation/final-review.md, including the Initial whole-feature review and Orchestrator triage, plus both workstream Resolution records. Inspect the cumulative branch diff against the starting commit. Verify every accepted Required finding and check those corrections for release-blocking defects and unnecessary compatibility machinery. Do not reopen optional suggestions or perform another open-ended review. Do not edit files. Return a final verdict and any remaining blockers with evidence." --model opus --effort medium --permission-mode plan
```

## Final verification

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

## Local browser validation gate

Run this gate after focused closure and any reviewed final corrections. The orchestrator records the
candidate commit in [plan.md](plan.md), then asks Aidan to validate it.

Prepare once:

```text
uv sync --locked
```

From `frontend/`:

```text
pnpm install --frozen-lockfile
```

Start the coordinator and console service in separate terminals from the repository root:

```text
uv run e87canbus run --profile simulator --reload
uv run e87canbus-console --port 8001
```

Start the frontend from `frontend/` in a third terminal:

```text
pnpm dev
```

Open `http://localhost:5173` and `http://localhost:5174`, then verify:

1. Both applications render without a browser-console error or permanent synchronization warning.
2. The coordinator Network panel shows one long-running coordinator `GET /api/live` request with
   `text/event-stream` and no `/socket.io` request.
3. The console Network panel shows two long-running `GET /api/live` requests at distinct origins:
   one to the coordinator backend and one through the local console origin. It shows no
   `/socket.io` or `/console/socket.io` request.
4. In development source maps, each stream's Network initiator reaches its generated Hey API SDK
   and `serverSentEvents.gen.ts`. The handwritten wrappers contain no raw `fetch`, `EventSource` or
   SSE parser.
5. Changing a remaining simulated vehicle control updates the coordinator projection immediately
   and the console's coordinator-backed display without a page reload or polling request.
6. The console's local CAN status reaches its expected connected or fault state from the local
   stream. A missing local `kcan` interface may report a fault; it must not remain unsynchronized.
7. The removed trace, connected-device, custom-CAN device and network-topology UI is absent.

Required evidence is Aidan's pass confirmation for all seven checks. On failure, capture the URL,
action, visible result, browser-console message and relevant Network request. Screenshots are useful
when the visible result is ambiguous but are not required for a pass.

Troubleshooting remains inside this gate. The resume condition is a passing candidate or Aidan's
explicit waiver. A correction that changes a public contract, architecture, security boundary or
accepted workstream returns to the orchestrator for a focused review before retesting.

## External validation record

- Status: `Pending`
- Candidate commit: `TBD`
- Aidan's result and evidence: `TBD`
- Troubleshooting and lasting decisions: `TBD`
- Resume condition met: `TBD`

## Initial whole-feature review

- Reviewer: `TBD`
- Branch, base and reviewed head: `feature/browser-sse`; base `4f3539d`; reviewed head
  `fb1bd7eae99a0a514b3b660dabcf9cbe9ae653db`.
- Verification run: `TBD`
- Acceptance-criteria audit: `TBD`
- Required findings by owner: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`
- Verdict: `TBD`

## Orchestrator triage

- Accepted findings and owners: `TBD`
- Rejected findings and reasons: `TBD`
- Deferred optional observations: `TBD`
- Drift requiring user decision: `TBD`

## Focused closure

- Reviewed head: `TBD`
- Finding outcomes: `TBD`
- Final simplification assessment: `TBD`
- Remaining blockers: `TBD`
- Verdict: `TBD`

## Orchestrator completion record

- Final head and verification: `TBD`
- External validation pending: `TBD`
- Specification drift: `TBD`
- Completion report delivered: `TBD`
