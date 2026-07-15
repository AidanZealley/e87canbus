# Phase 2: Revisioned application settings

## Goal

Add one authoritative, revisioned application-settings document to the existing SQLite database,
expose it through FastAPI and provide the frontend query/mutation boundary used by later car pages.
Theme remains browser-local and is not part of this document.

## Domain contract

Define framework-independent enums and an immutable settings value:

```text
SpeedUnit: mph | kmh
TemperatureUnit: c | f

ApplicationSettings
  revision
  speed_unit
  temperature_unit
  oil_warning_c
  oil_critical_c
  coolant_warning_c
  coolant_critical_c
  shift_stage_1_rpm
  shift_stage_2_rpm
  redline_rpm
  updated_at
```

Seed version 1 with:

| Field | Value |
|---|---:|
| Speed unit | `mph` |
| Temperature unit | `c` |
| Oil warning | 125 C |
| Oil critical | 135 C |
| Coolant warning | 105 C |
| Coolant critical | 115 C |
| Shift stage 1 | 6800 RPM |
| Shift stage 2 | 7000 RPM |
| Redline | 7200 RPM |
| Revision | 1 |

Validation belongs in the domain module and is callable without Pydantic or SQLite:

- Unit discriminators must be supported enum values.
- Temperatures must be finite and within `-40..250` C.
- Each warning value must be strictly below its matching critical value.
- RPM fields must be ordinary integers, not booleans, in `1000..12000`.
- `shift_stage_1_rpm < shift_stage_2_rpm < redline_rpm`.
- Revision and expected revision must be positive integers.
- UTC timestamps use the same canonical convention as steering profiles.
- Reject invalid values; do not clamp, reorder or silently substitute defaults on writes.

Create a repository protocol with `get_settings()` and `update_settings(expected_revision,
candidate)` operations plus typed revision-conflict, corrupt-data and storage failures.

## SQLite ownership and migration

The existing file selected by `E87CANBUS_PROFILE_DATABASE` becomes the shared application database.
Keep that environment variable for compatibility.

Refactor initialization so a shared database adapter owns connection policy and migrations instead
of making the steering-profile repository responsible for the whole schema:

- Preserve migration 1's steering-profile table and seed behavior exactly.
- Set the supported migration version to 2.
- Migration 2 creates a singleton `application_settings` table and inserts the default row.
- Existing version-1 files upgrade in place without rewriting profiles.
- Fresh databases apply migrations in order and receive both seeds.
- Repeated startup is idempotent and must not restore user-edited settings.
- A database with a newer migration version fails closed.
- Keep WAL, `busy_timeout`, `synchronous = FULL`, short-lived operation connections and explicit
  transactions.

The settings update uses `BEGIN IMMEDIATE` and a conditional update on expected revision. It
increments revision exactly once and writes one new canonical timestamp. If no row matches, inspect
the current revision and raise the typed conflict without changing data.

Do not keep a transaction open while broadcasting or waiting on simulator ownership.

## FastAPI composition

Add a settings repository to app state. `create_app` accepts an independently injectable settings
repository for tests while default composition constructs it against the shared database. The
lifespan initializes the shared database once before serving requests.

Add strict Pydantic request models that reject unknown fields and map to the domain value rather
than replacing domain validation.

Endpoints:

```text
GET /api/settings
PUT /api/settings
```

`GET` returns the complete authoritative document. `PUT` accepts all editable fields plus
`expected_revision`; it never performs a partial update.

Error mapping:

| Condition | Status/code |
|---|---|
| Invalid body/domain value | 422 `validation_error` |
| Stale expected revision | 409 `settings_revision_conflict` |
| Storage unavailable/corrupt | 503 typed storage error |

The conflict envelope includes `current_revision`.

After commit, broadcast:

```json
{"type": "resources.changed", "resource": "settings", "id": null, "revision": 2}
```

Do not broadcast validation, conflict or persistence failures. The response contains the complete
committed settings, so the caller does not wait for its own invalidation event.

## Frontend API and query boundary

Create a typed settings API module with:

- Response and update-request types.
- `getApplicationSettings` and `updateApplicationSettings`.
- Shared error parsing consistent with current frontend APIs.
- A stable TanStack Query key/options factory.
- Compiled default settings matching the backend seed.

On successful PUT, replace the query cache with the response. Extend WebSocket event handling to
invalidate the settings query on the exact `resources.changed` settings event, allowing another
open display to refetch.

Later car screens consume an effective settings value:

- Authoritative query data when available.
- Compiled defaults when the query fails.
- A separate fault flag whenever defaults are being used because persistence is unavailable.

Do not place unsaved form drafts in the global query cache. Saving is disabled until an
authoritative revision has loaded.

## Canonical-unit behavior

SQLite and API thresholds remain Celsius regardless of display preference. Frontend editing in
Fahrenheit converts back to Celsius and rounds to the nearest 0.1 C on Save. Unit conversion
utilities belong with the Phase 5 presentation foundation, not in the persistence adapter.

## Tests

Domain:

- Default value is valid and stable.
- Every enum, finite/range, ordering and integer rule fails closed.
- Theme cannot appear in the settings contract.

SQLite:

- Fresh migration and seed.
- Exact version-1 to version-2 upgrade preserving profiles.
- Repeat initialization preserves edited settings.
- Round-trip and one-step revision increment.
- Stale writer loses and newer data remains.
- Concurrent same-revision writers allow exactly one success.
- Corrupt row and unsupported future migration fail safely.

API/publication:

- Exact GET/PUT serialization.
- 422 validation mapping.
- 409 conflict includes current revision.
- Successful update broadcasts once after commit.
- Failed update broadcasts nothing.
- Settings persist across app restart.
- Injected repositories remain usable in tests.

Frontend boundary:

- GET/PUT request shapes.
- Cache replacement on success.
- Invalidation on the WebSocket event.
- Defaults plus fault flag on load error.
- Failed mutation never appears saved.

## Completion criteria

- There is one domain-owned settings contract and one seed default.
- Existing databases upgrade without profile behavior drift.
- Settings survive restart and reject stale writes.
- API and WebSocket behavior allow multiple open displays to converge.
- Frontend consumers can distinguish authoritative settings from fallback defaults.
- Theme remains exclusively owned by the existing browser theme provider.
