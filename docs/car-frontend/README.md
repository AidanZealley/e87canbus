# Car frontend roadmap

This directory specifies the phased implementation of the routed development workbench and
in-car control centre. It is the source of truth for the intended behavior, ownership boundaries,
interfaces, sequencing and verification. It does not grant authority for live BMW decoding,
physical steering output or kiosk deployment.

## Product outcome

The React frontend will have three stable entry points:

- `/` is a development-only chooser between the two application modes.
- `/dev` preserves the current simulator workbench and adds deterministic controls for the new
  simulated telemetry and device-health states.
- `/car` is an 800x480-landscape-first in-car display with overview, drive, steering and settings
  views behind a dedicated icon navigation layout.

The coordinator will support the UI with simulation-only RPM and temperature messages, explicit
device-health projections and revisioned application settings stored in the existing SQLite file.
Missing or stale data is always represented honestly; it must never become a convincing numeric
zero in the car UI.

## Fixed decisions

- Use TanStack Router file-based routing and the Vite router plugin with automatic code splitting.
- Keep TanStack Query and the existing class-based shadcn theme provider above the router.
- Keep theme choice in browser `localStorage`; it is not an application setting.
- Optimize car layouts for 800x480 landscape without enforcing a fixed control size in code or
  tests. Final control density is tuned manually on the target display.
- Use existing shadcn design tokens or named Tailwind colors. Do not introduce raw page-specific
  color values.
- The car sidebar is always visible and icon-only. It contains Overview, Drive, Steering and
  Settings, with no visible route to development mode.
- Kiosk mode loads `/car`, but Pi service and Chromium startup configuration are outside this
  roadmap.
- Canonical backend units remain km/h, degrees Celsius and integer RPM.
- Persist speed and temperature unit preferences independently.
- Temperature warning demotion uses fixed 3 degrees Celsius hysteresis.
- Engine telemetry becomes stale after one coordinator-evaluated second.
- Steering editing and settings remain available at any speed.
- Car steering edits require confirmation to activate and never overwrite a saved profile.
- Simulated degraded/offline states are UI test inputs, not real diagnostic criteria.

## Phases

| Phase | Document | Outcome | Depends on |
|---:|---|---|---|
| 1 | [Routing and layouts](01-routing-and-layouts.md) | Routed mode chooser, `/dev`, `/car` shell and shared theme control | Existing frontend |
| 2 | [Application settings](02-application-settings.md) | Revisioned SQLite settings, API and frontend settings data flow | Phase 1 for final UI placement |
| 3 | [Engine telemetry simulation](03-engine-telemetry-simulation.md) | RPM/oil/coolant through the normal simulation pipeline | Existing coordinator architecture |
| 4 | [Device health](04-device-health.md) | Explicit device status contract and simulator controls | Existing simulator snapshots |
| 5 | [Car UI foundation](05-car-ui-foundation.md) | Shared car data provider, conversions, warnings and instruments | Phases 1-4 |
| 6 | [Car screens](06-car-screens.md) | Overview, drive, steering and settings experiences | Phase 5 |
| 7 | [Verification and acceptance](07-verification-and-acceptance.md) | Repository checks and 800x480 visual acceptance | Phases 1-6 |

Phases 2, 3 and 4 may be implemented independently after their current-code prerequisites are
confirmed. Their composition changes must be coordinated because each touches the FastAPI
application and simulator snapshot contract. Phases 5 and 6 must not start against invented local
data shapes; consume the committed contracts from the earlier phases.

## Cross-phase architecture

```text
Development controls
  -> FastAPI simulator command
  -> single-owner simulation engine
  -> simulation-only CAN frame / explicit device state
  -> normal application transition and snapshot projection
  -> HTTP snapshot + WebSocket publication
  -> TanStack Query cache
  -> long-lived /car layout provider
  -> overview / drive / steering / settings views
```

Application settings use a parallel persistence path:

```text
/car/settings local draft
  -> revisioned PUT /api/settings
  -> settings domain validation
  -> short SQLite transaction
  -> committed authoritative response
  -> cache replacement + WebSocket invalidation for other clients
```

Keep current ownership rules intact:

- Pure domain and application transitions do not import FastAPI, SQLite or React concerns.
- Synthetic telemetry enters through `SimulationProtocolRouter`; the live `ProtocolRouter` must
  not decode simulation identifiers.
- Runtime mutation remains submitted to the bounded single-owner queue.
- SQLite transactions never span runtime or WebSocket work.
- React components do not manufacture backend-valid state when the backend reports unavailable.

## Public contracts introduced by the roadmap

Frontend routes:

```text
/
/dev
/car
/car/drive
/car/steering
/car/settings
```

HTTP resources:

```text
GET  /api/settings
PUT  /api/settings
POST /api/vehicle/rpm
POST /api/vehicle/rpm/silence
POST /api/vehicle/oil-temperature
POST /api/vehicle/oil-temperature/silence
POST /api/vehicle/coolant-temperature
POST /api/vehicle/coolant-temperature/silence
PUT  /api/simulation/devices/{device_id}/status
```

Snapshot additions:

- `application.engine.rpm`
- `application.engine.oil_temperature_c`
- `application.engine.coolant_temperature_c`
- top-level `devices`

WebSocket event addition:

- `application_settings_changed`

The phase documents define the complete shapes and failure behavior.

## Working method

Give an implementation agent one phase at a time using
[stage-agent-prompt.md](stage-agent-prompt.md). Before implementation, the agent must inspect the
current repository because these documents specify required behavior, not permission to overwrite
newer architecture. After a meaningful phase or slice, update
[implementation-log.md](implementation-log.md) with factual changes and verification evidence.

Do not mark a phase `Verified` merely because focused tests pass. Verification also requires every
completion criterion in its phase document and the relevant repository-wide checks. Phase 7 owns
the final integrated visual acceptance.

## Global non-goals

- Verified BMW RPM, oil-temperature or coolant-temperature CAN identifiers.
- Production CAN decoding for those signals.
- Real device heartbeat intervals or degraded/offline thresholds.
- Raspberry Pi kiosk startup, browser flags, display brightness integration or systemd services.
- Authentication or non-loopback deployment policy.
- Physical Servotronic command values, controller transport or live transmit authority.
- Automatic driving-state restrictions.
- Browser E2E framework adoption.
- Automated pixel-size assertions for touch controls.

