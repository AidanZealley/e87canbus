# Browser SSE implementation plan

Status: in progress.

## Orchestration record

- Integration branch: `feature/browser-sse`
- Starting commit: `4f3539d`
- Orchestrator: `Codex in T3 Code`
- Review command: packet-specific Claude Code command using `--model opus --effort medium --permission-mode plan`
- Specification approved at commit: `2ab06f36b141c941824195cb818b5cce1a48aa26`
- Started: `2026-09-16`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Retire legacy live UI](01-retire-legacy-live-ui.md) | Approved Slice 01 | Accepted | `77e97e7` |
| 2 | [Coordinator SSE server and contract](02-coordinator-sse-server.md) | Workstream 1 | Accepted | `53d5950` |
| 3 | [Coordinator browser cutover](03-coordinator-browser-cutover.md) | Workstream 2 | Accepted | `39ec497` |
| 4 | [Console SSE server and contract](04-console-sse-server.md) | Workstream 3 | Accepted | `8e64ab4` |
| 5 | [Console browser cutover](05-console-browser-cutover.md) | Workstream 4 | Accepted | `82954b6` |
| 6 | [Final transport cleanup](06-final-transport-cleanup.md) | Workstream 5 | Accepted | pending implementation commit |

## Why these boundaries

Workstream 1 removes frontend consumers of trace and registry state while the current transport is
still stable. That keeps deletion and replacement reasoning out of the SSE reviews.

Each host then has separate server-contract and browser-cutover workstreams. The server workstream
adds SSE beside the old path for one accepted commit. The following browser workstream switches its
host and removes that host's old path. This temporary overlap is a migration boundary, not a
compatibility feature or reusable dual-transport design.

Workstream 6 removes only shared leftovers after both hosts have cut over. Its review is dominated
by searches, dependency checks and documentation agreement rather than live behavior. These smaller
units cost more fixed review calls, but constrain the implementation and remediation context that
caused earlier token pressure.

## Cross-workstream contracts

- Each host exposes `GET /api/live`, but each has its own origin, OpenAPI document and event union.
- SSE uses one JSON `data` line per record, a blank line terminator, idle comments, no event IDs and
  no replay buffer.
- Registration and the initial complete snapshot are atomic. Each subscriber has bounded pending
  output. Publication never waits on a browser.
- A browser reconnects after HTTP failure, read failure, idle timeout or clean EOF and treats the
  next snapshot as authoritative.
- The console frontend consumes the coordinator API through the configured coordinator origin. Its
  local console-host client remains same-origin, so identical `/api/live` paths do not collide.
- Generated Hey API operations, types and Zod validators are the only editable-contract derivative.
  A streamed record must pass its generated validator before it changes application state.
- Hey API owns SSE transport, parsing and generated validation. It does not own retained projection
  state or expose an SSE stream as a TanStack Query.
- One compact Zustand store retains coordinator projections and connection state because both apps
  have many selective consumers. TanStack Query remains reserved for finite HTTP resources and
  mutations. Remove revisions, protocol compatibility, trace and registry state from the store.
- Server workstreams may keep one host's old path only until its immediately following browser
  cutover. Workstream 6 must not discover a live consumer of the retired transport.

## Ownership handoffs

Workstream 1 owns removal of legacy frontend consumers. It leaves the old generated contract and
backend simulation machinery intact for later deletion or migration.

Workstream 2 owns the coordinator SSE models, publisher, endpoint, OpenAPI output and generated Hey
API operation. Workstream 3 consumes that seam, owns the coordinator reconnect wrapper and Zustand
store, and removes the coordinator Socket.IO path and bespoke coordinator contract.

Workstream 4 owns the separate console-host SSE models, endpoint, OpenAPI output and generated Hey
API operation. Workstream 5 consumes that seam, owns the local browser state and routing, and removes
the console-host Socket.IO path and bespoke console contract.

Workstream 6 owns shared dependency, configuration, diagnostics, script, lockfile and documentation
cleanup. Contract defects return to the workstream that owns the contract rather than being changed
silently during cleanup.

## Whole-feature acceptance

- Both browser applications start each host connection from a complete generated and validated SSE
  snapshot.
- Coordinator projections and durable resource invalidations arrive without polling.
- The console browser holds one coordinator stream and one local console-host stream.
- All four termination modes reconnect and converge on a fresh snapshot.
- Slow subscribers cannot block publication or create an unbounded queue.
- Socket.IO, Engine.IO, protocol-version envelopes, resync messages, trace subscriptions, bespoke
  live schemas and live-contract generators are absent.
- The live trace UI, driving-console device view, and legacy simulator device and topology UI are
  absent. Internal simulation trace and custom-CAN protocol coverage remain.
- Targeted checks and the final repository checks pass.

## External validation gates

| Gate | Owner | Placement | Status | Candidate | Resume condition |
|---|---|---|---|---|---|
| Local browser SSE validation | Orchestrator and Aidan | After whole-feature closure, before completion | Pending | `TBD` | Aidan reports every required browser check passed, or explicitly waives the gate |

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-16 | Remove legacy custom-CAN simulator device and topology UI instead of replacing its live registry data | The app is unused and later slices introduce independent device simulations | Aidan | 1 |
| 2026-09-16 | Split each host's server contract from its browser cutover and reserve final cleanup for a sixth workstream | Smaller implementation and remediation contexts are worth the temporary migration overlap | Aidan | 2-6 |
| 2026-09-16 | Keep one reduced Zustand coordinator store | Hey API generates transport and validation but does not retain live projections or integrate SSE state with TanStack Query | Aidan and local generated-client inspection | 3 |
