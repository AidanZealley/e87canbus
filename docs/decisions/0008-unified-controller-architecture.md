# ADR 0008: Converge live and simulated control into one modular controller

- **Status:** Accepted
- **Date:** 2026-07-15

## Context

The repository currently has a deterministic single-owner kernel, a capability-controlled live
runner and a production-path simulator, but the live runner and simulator API still construct
separate application lifecycles and expose different transport concerns. Later work needs stable
runtime and publication contracts before those compositions can converge without weakening the
safety boundaries in ADRs 0001-0006.

The browser currently receives complete simulator snapshots and trace entries over a bounded raw
WebSocket, while settings and steering profiles use HTTP and SQLite. This behavior must remain
available during the migration. ADR 0007 remains Proposed and its physical steering protocol is
not authorized by this decision.

## Decision

Live and simulated operation will converge into one modular controller process and lifecycle.
Physical, simulated and observer behavior is selected through adapters; adapters and transport
handlers never mutate operational state directly. One bounded, ordered `ControllerInput` path and
one controller owner remain the only operational-state mutation boundary. Simulation replaces
external adapters and devices and continues to use the real wire codecs, routing, transitions,
commits, effect execution and output policy.

HTTP owns semantic business commands and durable-resource CRUD. One Socket.IO namespace will own
server-to-browser live-state replication. Socket client events may select transport concerns such
as diagnostic subscriptions, but are not business commands. The frontend will hold current live
state in Zustand and HTTP server state in TanStack Query. Every new or unrecoverable socket
connection receives a complete current snapshot; live publications and diagnostic traces remain
bounded and telemetry may be coalesced to a bounded latest-state rate.

Each device capability has exactly one ingress authority. Read-only observers may mirror state but
cannot originate a second stream for that capability. Physical and emulated repository-owned
devices use the same codec and controller path, and desired state remains distinct from observed
state when a device supplies no acknowledgement.

The framework-independent runtime vocabulary is:

- `ControllerInput` is a closed union covering startup, shutdown, routed timestamped CAN frames,
  timer decisions, timestamped runtime/profile activation, current semantic commands and typed
  reader, inbox, effect and actuator failures. It contains no FastAPI request, Socket.IO session or
  simulator UI value.
- A `Commit` is returned only after controller state is mutated. Its revision is monotonic within
  one controller boot, its snapshot is the complete immutable application projection, its effects
  are ordered desired external actions, and its `changed_topics` is a closed set derived from
  projection differences. `state_changed` may remain as a convenience value. A commit does not
  imply effect success; failures return later through `ControllerInput`.
- The application snapshot does not duplicate projections owned elsewhere. The complete desired
  button LED snapshot remains a deterministic projection of application steering state and an
  atomic effect. Observed device state belongs to selected device adapters, and runtime health
  belongs to immutable diagnostics. The controller service composes those values for publication;
  a kernel startup therefore marks only the projections the kernel can currently supply and does
  not fabricate a `devices` change.
- Controller state topics are the fixed values `vehicle`, `engine`, `steering`, `buttons`,
  `devices` and `health`. They are projection hints, not runtime-registered topics or a generic
  internal bus. Durable resource changes come from repository/application services, and bounded
  trace batches come from diagnostics rather than fabricated controller-state changes.
- Every controller-service start creates a new opaque `boot_id`. Revisions are monotonic only
  within that boot. A simulation reset may additionally create a simulation `session_id`; its
  trace position remains the bounded pair `(session_id, sequence)`. The service trace sequence is
  similarly scoped to its owning boot/session and retained only to its configured bound.
- Monotonic time is used for ingress, freshness, timeouts and latency. Canonical UTC is used only
  for externally emitted timestamps and durable records.

The version 1 live envelope is specified for later transport work as:

```json
{
  "protocol_version": 1,
  "boot_id": "opaque",
  "revision": 42,
  "emitted_at": "2026-07-15T12:34:56.000000Z",
  "data": {}
}
```

Consumers compare revisions only when `boot_id` matches and retain the last applied revision for
each topic independently. A changed `boot_id` invalidates every previously retained live revision.
Topic payloads are complete values, not JSON patches. Unknown protocol versions fail visibly; a
consumer must not guess their meaning. Pydantic boundary models adapt the framework-independent
snapshot rather than duplicating a second handwritten domain model.

ADRs 0001-0006 continue to govern ordering, output grants, simulation, generated protocol, atomic
LED state and hardware evidence. Default live composition remains unable to transmit. This ADR
does not accept ADR 0007, select a BMW identifier or authorize physical steering output.

## Consequences

- Process composition, HTTP commands/resources, Socket.IO publication and frontend ownership can
  migrate in later phases against stable input, commit, identity and topic semantics.
- Existing HTTP and raw-WebSocket simulator payloads remain temporary compatibility surfaces.
  They are not the version 1 live envelope and Phase 8 removes them after consumers move.
- The current kernel records CAN-effect and actuator failures in diagnostics without returning a
  commit or incrementing revision. Therefore those failures cannot yet produce a `health` changed
  topic. Phase 7 must reconcile health with the final commit/publication contract while preserving
  non-recursive failure feedback.
- The current simulation session uses an integer identity. It remains distinct from the future
  opaque controller-service `boot_id`; Phase 2 introduces service identity and Phase 4 exposes it.
- Generic brokers, runtime event registration, event sourcing, a separate simulator state owner
  and a full-car simulation are rejected. They add ownership or retention complexity without
  improving the required controller behavior.

## Implementation note — 2026-07-15

Phase 8 completed the planned cutover. The raw `/ws` endpoint, `GET /api/snapshot`, simulator
response snapshots, compatibility connection manager and second publication queue are removed.
Current browser live state flows only from Socket.IO into Zustand; durable HTTP resources remain in
TanStack Query. Development HTTP actions return only `accepted` and the stable process `boot_id`,
while revisioned/session-scoped authority arrives through Socket.IO rather than an HTTP facade.
