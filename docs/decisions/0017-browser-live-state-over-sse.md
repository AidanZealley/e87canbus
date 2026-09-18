# ADR 0017: Browser live state over SSE

- **Status:** Accepted
- **Date:** 2026-09-18
- **Partially supersedes:** [ADR 0008](0008-unified-controller-architecture.md), which selected
  Socket.IO for browser live-state replication. Its controller ownership, bounded publication and
  frontend state ownership remain in force.
- **Partially superseded by:** [ADR 0018](0018-simplify-coordinator-before-independent-devices.md),
  which removes the registry and applied-device projections that this record left in the backend.

## Context

The coordinator and console host used Socket.IO only for server-to-browser state. Commands and
durable resources already used HTTP. The socket contract also had its own event registries, JSON
schemas and code generator beside the OpenAPI clients.

The browser needs current state, not event history. Each host can produce a complete snapshot when
a client connects, so replay IDs and a bidirectional socket protocol add no useful behavior.

## Decision

Each host publishes browser live state through its own `GET /api/live` SSE endpoint. The
coordinator stream carries a complete initial snapshot, complete projection replacements and
durable-resource invalidations. The console-host stream carries complete local CAN snapshots. The
console browser consumes both origins; the coordinator browser consumes only the coordinator.

FastAPI models and each host's OpenAPI document are the contract source. Hey API generates the
stream operation, TypeScript types and Zod validators. Browser code validates every record before
it replaces Zustand state. There is no separate live schema or generator.

Every connection starts with an authoritative complete snapshot. Streams do not use event IDs or
replay. A small application-owned wrapper reconnects after HTTP failure, read failure, idle timeout
or clean EOF. Reconnection is bounded per generated stream attempt, and retained values remain
unavailable until the next snapshot arrives.

Publication never waits for a browser. Each subscriber has bounded pending output; a slow client is
disconnected and recovers through a new snapshot. Commands and durable-resource operations remain
HTTP.

## Consequences

- Socket.IO, Engine.IO and the bespoke browser live-contract pipeline are removed.
- Browser stores contain current state and connection state, without protocol versions, replay
  positions or resync messages.
- The browser CAN trace, connected-device projection and custom-CAN topology UI are removed. The
  bounded backend trace and CAN registry remain for simulation, protocol tests and current physical
  devices.
- Host-local contracts remain separate even though both endpoints use SSE.
- A host restart or dropped connection loses intermediate events by design. The next complete
  snapshot restores current state.
