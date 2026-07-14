# Phase 4: Profile API and publication

## Goal

Expose saved-profile CRUD and runtime activation through FastAPI. Join the persistence and runtime
boundaries without allowing HTTP concurrency to bypass either one's ownership rules.

## API resources

Recommended initial endpoints:

```text
GET    /api/steering/profiles
POST   /api/steering/profiles
GET    /api/steering/profiles/{profile_id}
PUT    /api/steering/profiles/{profile_id}
DELETE /api/steering/profiles/{profile_id}
GET    /api/steering/curve-state
POST   /api/steering/curve-state/activate
```

Avoid an endpoint named `save-and-activate` initially. Save and activation have different owners
and failure modes. The frontend can offer a convenience button while showing the result of each
operation explicitly.

### Definition JSON

Use one request/response shape everywhere:

```json
{
  "schema_version": 1,
  "interpolation": "linear-v1",
  "points": [
    {"speed_deci_kph": 0, "assistance_per_mille": 1000}
  ]
}
```

Responses may include display projections such as `speed_kph` and `assistance_percent`, but clients
must submit and compare authoritative integer values.

### Saved profile update

```json
{
  "expected_revision": 3,
  "name": "Dry track",
  "definition": {
    "schema_version": 1,
    "interpolation": "linear-v1",
    "points": [
      {"speed_deci_kph": 0, "assistance_per_mille": 1000}
    ]
  }
}
```

The point array is abbreviated in these examples; real requests must contain the complete fixed
grid selected in Phase 1.

Successful create/update returns the complete committed profile. Use a consistent error envelope
for validation, not-found, name-conflict and revision-conflict responses. A conflict response should
include the current saved revision so the UI can offer reload rather than guessing.

### Activation request

Activation accepts a complete definition plus optional saved provenance:

```json
{
  "definition": {
    "schema_version": 1,
    "interpolation": "linear-v1",
    "points": [
      {"speed_deci_kph": 0, "assistance_per_mille": 1000}
    ]
  },
  "saved_profile_id": "optional-id",
  "saved_profile_revision": 3
}
```

The service must verify that claimed saved provenance matches the repository definition. If it
doesn't, either reject the claim or activate without saved provenance; never publish a false match.

The activation response returns authoritative curve state, including activation status and
revision. In the current in-process implementation it completes as `active`. The contract reserves
`activating` and `activation_failed` for a future device consumer.

## Draft, Apply and Save semantics

- Dragging: browser-only draft.
- Apply: send the draft definition to activation; no SQLite write.
- Save new: create a saved profile; no activation.
- Save changes: update a saved profile using `expected_revision`; no activation.
- Revert to active: replace browser draft from `curve-state`; no backend mutation.
- Load saved: replace browser draft from a selected saved profile; no activation.

The UI may expose `Save and apply`, but it is a two-result workflow: save first, then activate the
exact committed definition and provenance. If activation fails, the profile remains saved and the
UI reports that it is not active.

## Concurrency and ownership

Profile repository operations may be serialized through an API-owned lock or executed using
separate safe SQLite connections. Activation must be submitted to the runtime's bounded owner and
may return overload rather than waiting indefinitely.

Do not hold a SQLite transaction open while waiting for runtime activation. No transaction can be
atomic across SQLite and a future physical controller; represent partial success honestly.

Suggested HTTP mappings:

| Condition | Status |
|---|---:|
| Invalid definition/name | 422 |
| Missing profile | 404 |
| Name or expected-revision conflict | 409 |
| Runtime command queue full | 503 |
| Activation consumer rejects/fails | 409 or 503, with typed detail |

## WebSocket publication

Publish the full active curve projection in authoritative snapshots. Additionally publish a
profile-catalog invalidation or revision event after saved CRUD so other open displays can refetch
the list.

Do not broadcast every drag movement. WebSocket reconnect must recover from a missed event using a
full snapshot plus a fresh profile list request.

## Security and deployment boundary

The current development CORS policy and unauthenticated simulator API are not authority for an
in-car writable deployment. Before binding beyond loopback, define authentication, origin policy
and whether curve editing is permitted while moving. That policy is separate from domain
validation.

## Tests

- CRUD happy paths and exact response serialization.
- Every domain validation error maps consistently.
- Stale update/delete returns conflict and preserves the newer row.
- Apply changes active state without creating/updating a saved row.
- Save does not change active state.
- Save then failed activation reports the split result honestly.
- False saved provenance is rejected or removed.
- Concurrent updates allow exactly one expected revision to win.
- Activation queue overload is bounded and reported.
- WebSocket snapshot/reconnect contains authoritative active state.
- Saved catalog changes cause a refetch signal without transmitting draft state.

## Completion criteria

- The browser has all required contracts for Phase 5.
- API handlers contain orchestration only; domain, SQLite and kernel rules remain in their layers.
- Save and activation are observably distinct.
- No HTTP concurrency path can mutate runtime state outside the single owner.
