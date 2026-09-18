# Browser SSE whole-feature review

Status: local browser validation pending.

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

- Reviewer: Claude Code, Opus, medium effort, read-only plan mode.
- Branch, base and reviewed head: `feature/browser-sse`; base `4f3539d`; reviewed head
  `f95f50ed2a25ced29f2b7cf225f04a97aae808c0`.
- Verification run: All final-review commands passed: custom protocol drift; 960 backend tests;
  mypy; Ruff; both import contracts; diff check; both API drift paths; frontend typecheck, lint, 158
  tests and both builds. The coordinator build retained its known chunk-size warning.
- Acceptance-criteria audit: Host lifecycles, authorization, atomic snapshots, bounds, generated
  OpenAPI/Zod seams, distinct origins, Zustand scope, dependency removal, deleted UI and current
  documentation matched the approved sources. Reconnect behavior works for all four termination
  modes, but production configuration and tests did not directly verify generated-client ownership
  of HTTP and read failures.
- Required findings by owner: Workstream 3 must set `sseMaxRetryAttempts: 1` for the coordinator
  generated operation and test rejected HTTP/fetch plus mid-stream read failures. Workstream 5 must
  make the same correction and tests for the local console operation. This removes nested indefinite
  generated retries and makes the wrapper the bounded owner of all four reconnect modes.
- Optional observations: The local console store retains unused status/error detail; deletion-only
  negative UI assertions remain; generated clients expose simulator operations without current UI
  consumers; the coordinator publisher wakes at its telemetry cadence while idle.
- Questions: `health.devices` is approved per-role runtime fault health, not the removed live device
  registry. Removing the coordinator steering editor was intentional with the legacy Servotronic
  card; the driving console retains curve editing.
- Verdict: Approve after the two owner-assigned reconnect corrections and focused closure.

## Orchestrator triage

- Accepted findings and owners: Workstream 3 owns the coordinator retry option and failure tests;
  Workstream 5 owns the equivalent local console correction.
- Rejected findings and reasons: No change to health projections or coordinator editor ownership;
  both match approved scope. No generated-runtime fork or shared reconnect framework.
- Deferred optional observations: Local status detail, deletion-only test assertions, unused
  generated simulator operations and idle publisher wakeups do not block acceptance.
- Drift requiring user decision: None.

## Correction evidence

- Workstream 3: The coordinator wrapper passes `sseMaxRetryAttempts: 1` and treats the generated
  error as the terminal result of that attempt without replacing it with a clean-EOF error. Focused
  request- and mid-stream read-failure tests hold the wrapper at its 3-second delay, confirm visible
  failure and retained valid state, then confirm reconnection starts from a fresh snapshot.
- Workstream 3 verification: coordinator-client passed 8 files and 20 tests plus typecheck;
  coordinator passed 11 files and 38 tests; console passed 25 files and 102 tests;
  `git diff --check` passed.
- Workstream 5: The local console wrapper passes `sseMaxRetryAttempts: 1` and retains the generated
  terminal error through its wrapper-owned delay. Focused request- and mid-stream read-failure tests
  confirm visible failure, retained valid CAN state, and reconnection from a fresh complete snapshot.
- Workstream 5 verification: console passed 25 files and 104 tests plus typecheck and build;
  coordinator-client passed 8 files and 20 tests plus typecheck; `git diff --check` passed.

## Focused closure

- Reviewed head: `1f7c2df78354a39bdc413b37885f916509643e31` plus the uncommitted Workstream
  3 and 5 correction diff.
- Finding outcomes: Both wrappers set `sseMaxRetryAttempts: 1`, preserve generated HTTP/read errors
  through the wrapper delay and reconnect from a fresh complete snapshot. Focused request and
  mid-stream failure tests passed for both hosts.
- Final simplification assessment: Each direct host wrapper gained one local failure flag and one
  fixed generated-attempt bound. No shared framework, generated-runtime fork, compatibility path or
  configuration point was added.
- Remaining blockers: None before final verification and the documented local browser gate.
- Verdict: Approved. No remaining Required findings.

## Orchestrator completion record

- Final head and verification: Pending correction commit hash. Final commands passed: custom
  protocol drift, 960 backend tests, mypy, Ruff, two import contracts, diff check, both API drift
  paths, frontend typecheck/lint, 162 frontend tests and both production builds. The coordinator
  build retains its known chunk-size warning.
- External validation pending: The documented seven-check local browser gate.
- Specification drift: None.
- Completion report delivered: `TBD`
