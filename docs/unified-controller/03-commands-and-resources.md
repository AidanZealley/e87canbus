# Phase 3: HTTP commands and durable resources

## Goal

Establish one typed HTTP boundary for operational commands and one precise resource boundary for
durable settings/profiles. Eliminate backend request handlers that directly own runtime changes and
prepare the frontend migration without yet removing compatibility responses it still consumes.

This phase does not move live state into Zustand, add Socket.IO or grant physical output.

## Preconditions

- Phase 2 unified composition is `Verified`.
- Current steering, button, simulated vehicle, settings and profile routes have been inventoried.
- Current frontend consumers and mutation invalidation behavior are known.

## Command taxonomy

Separate two kinds of action explicitly.

### Semantic operational commands

These express controller intent and enter the controller-service inbox:

```text
SetMaximumAssistance(enabled)
SetSteeringMode(mode, optional_manual_level)
ActivateSteeringProfile(profile identity/revision)
```

Use current feature semantics and domain validation. Do not add commands for speculative hardware.
Commands set desired state; avoid `toggle` endpoints and command names.

Suggested routes:

```text
PUT  /api/commands/maximum-assistance
PUT  /api/commands/steering-mode
POST /api/commands/activate-steering-profile
```

An accepted command response is small and explicit:

```json
{
  "accepted": true,
  "boot_id": "opaque",
  "revision": 42
}
```

The authoritative resulting live projection arrives through the publication path. Until Phase 5
moves the frontend, compatibility endpoints may additionally return the old snapshot shape, but no
new consumer should depend on it.

### Development adapter actions

Development routes operate selected emulators or signal sources:

```text
PUT  /api/dev/simulation/vehicle/speed
PUT  /api/dev/simulation/vehicle/rpm
PUT  /api/dev/simulation/vehicle/oil-temperature
PUT  /api/dev/simulation/vehicle/coolant-temperature
POST /api/dev/simulation/devices/button-pad/buttons/{index}/tap
POST /api/dev/simulation/reset
```

Exact naming should minimize unnecessary churn, but development-only ownership must be obvious.
These actions submit typed runtime work. They never directly dispatch domain events or edit state.
Routes fail explicitly when their required simulated adapter is not composed.

## Command gateway behavior

One small command service/gateway should:

- Validate domain values before queuing when possible.
- Reject work when the bounded runtime inbox is full.
- Await the matching result with a finite timeout.
- Map validation, unavailable capability, conflict, overload and runtime failure to stable errors.
- Never hold a SQLite transaction while waiting for the controller.
- Never retry a potentially side-effecting command invisibly.

Use an interface only if it is the real API-to-runtime ownership seam. Avoid a hierarchy of one-line
command handler classes.

## Durable resources

Settings and steering profiles remain revisioned SQLite resources:

```text
GET/PUT     /api/settings
GET/POST   /api/steering/profiles
GET/PUT/DELETE /api/steering/profiles/{id}
```

Resource mutation requirements:

- Strict request models reject unknown fields.
- Domain validation remains callable without FastAPI/Pydantic.
- Expected revision conflicts fail without overwriting the winner.
- Transactions are short, explicit and complete before runtime or publication work.
- The response contains the complete committed resource.
- A resource that changes active runtime configuration submits a typed configuration input after
  persistence and before returning success.
- Startup reconciles persisted desired configuration after a crash between persistence and runtime
  application.

Theme and frontend drafts remain browser-local.

## Precise resource change notifications

Define a typed invalidation model for other clients:

```json
{
  "resource": "settings",
  "id": null,
  "revision": 3
}
```

or:

```json
{
  "resource": "steering_profile",
  "id": "profile-id",
  "revision": 7
}
```

The mutation initiator uses the returned resource to update its Query cache. Publication exists so
other clients can invalidate only the exact affected query. Do not emit a generic refresh-all
event.

Phase 4 transports this model over Socket.IO. Existing WebSocket invalidations may temporarily
carry an adapted equivalent.

## Error contract

Keep one problem envelope and stable codes for:

- Validation failure: 422.
- Revision conflict: 409 with current revision.
- Required adapter/capability absent: 409 or 503, selected consistently.
- Runtime inbox full or command timeout: 503.
- Controller session failed/not ready: 503.
- Storage unavailable/corrupt: 503.

Command timeout does not prove the command was not processed. Prefer naturally idempotent set
commands so a caller may explicitly reconcile and retry.

## Frontend preparation

Add or normalize typed API functions and TanStack Query options/mutations without switching live
snapshot ownership yet:

- All low-level HTTP goes through the shared API client.
- Query keys are stable and domain-specific.
- Mutations return typed command acknowledgements or committed resources.
- Successful resource mutations replace exact cache data.
- No new broad invalidation is introduced.

Direct `fetch` inside the API client remains expected. Direct `fetch` from components, providers or
event handlers is not permitted.

## Tests

- Semantic commands submit exactly one typed runtime input and return its boot/revision.
- Repeating each set command is safe and does not reverse state.
- Runtime overload/timeout/unavailable capability maps to the documented problem.
- Emulator actions traverse virtual CAN where required and fail when the emulator is absent.
- Resource writes preserve revision/conflict/transaction behavior.
- Active configuration mutation is applied through the runtime owner.
- Mutation response carries the committed resource.
- Precise invalidation identifies only the changed resource.
- Existing consumers remain compatible through explicitly temporary behavior.
- Frontend API/query unit tests prove exact paths, bodies, cache replacement and errors.

## Completion criteria

- Every current user-initiated runtime change has one typed command or development-action path.
- No HTTP route mutates controller state directly.
- Operational commands are explicit, idempotent and return a small acknowledgement.
- Durable resources retain revisioned SQLite ownership and precise cache semantics.
- Broad refresh-all invalidation is no longer added by backend mutations.
- Compatibility behavior and Phase 5/8 removal ownership are documented.
- No live transmit or new physical steering behavior is introduced.
- Focused and relevant repository-wide checks pass.
