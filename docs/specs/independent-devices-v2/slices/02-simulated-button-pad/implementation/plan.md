# Simulated independent button pad implementation plan

Status: draft; implementation has not started.

## Orchestration record

- Integration branch: `TBD` (`feature/simulated-button-pad` when started)
- Starting commit: `TBD` (must contain the accepted Slice 1.5 implementation)
- Orchestrator: `TBD`
- Review command: packet-specific Claude Code command using `--model opus --effort medium --permission-mode plan`
- Specification approved at commit: `TBD` after Slice 1.5 documentation approval
- Started: `TBD`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Define the independent button-pad scene](01-define-button-pad-scene.md) | Completed Slice 1.5 | Not started | — |
| 2 | [Authenticate role-bearing devices](02-authenticate-role-bearing-devices.md) | Workstream 1 | Not started | — |
| 3 | [Persist device configuration and status](03-persist-device-state.md) | Workstream 2 | Not started | — |
| 4 | [Accept device status and button presses](04-device-http-inputs.md) | Workstream 3 | Not started | — |
| 5 | [Synchronize durable device configuration](05-synchronize-device-configuration.md) | Workstream 4 | Not started | — |
| 6 | [Expose device configuration over SSE](06-expose-device-configuration-sse.md) | Workstream 5 | Not started | — |
| 7 | [Run the simulated pad through the production API](07-simulated-button-pad-client.md) | Workstream 6 | Not started | — |

## Why these boundaries

Slice 1.5 owns all deletion and coordinator simplification. This workflow starts from that accepted
boundary and builds only the independent button-pad path.

Workstream 1 gives the complete device document one explicit owner without mixing it with transport,
storage or identity. Workstream 2 establishes certificate identity without opening a route.
Workstream 3 owns the one SQLite migration and durable generation rules. Workstream 4 adds the finite
HTTP inputs and the one canonical controller input. Workstream 5 owns durable synchronization and
bounded subscription ordering. Workstream 6 is the thin public and deployment edge around that seam.
Workstream 7 consumes all production seams and adds only the independent in-process client.

The seven packets keep scene semantics, persistence and concurrency, the ASGI stream boundary and
simulator lifecycle in separate review contexts. Combining the scene with authentication or storage
would obscure a contract used by every later workstream.

## Cross-workstream contracts

- The accepted Slice 1.5 result is not migration scaffolding. CAN in the coordinator means
  communication with the car; no project device is discovered, configured, commanded or observed
  through it.
- `DeviceRole` is a lean closed identity value using the canonical certificate spellings
  `button-pad` and `servotronic-controller`; it is not a registry or device catalogue.
- `PrincipalKind.DEVICE` carries a canonical UUID device ID and a `DeviceRole`. Request bodies and
  query parameters never supply either identity value.
- Only the button-pad role has a configuration or status schema in this slice. A Servotronic
  certificate authenticates but receives `403` from role-specific device behavior until Slice 6.
- The device scene has exactly 16 entries, global brightness `255`, resolved current colours and
  active-only animations. It excludes transient coordinator press-feedback overlays.
- Desired steering state and curve/profile data remain as delivered by Slice 1.5, with no device
  output or applied-state acknowledgement until Slice 6.
- The SQLite generation is a per-device JSON-safe integer. Creating the first role-default envelope
  writes its initial generation once; reconnect, restart and identical desired documents do not
  advance it. Changed complete documents advance it atomically and never wrap.
- Device status is last-reported diagnostic data with coordinator UTC receipt time. It has no
  heartbeat, expiry or presence meaning.
- Direct HTTP button input uses one canonical `ButtonPressed` value and the controller inbox once.
  There is no CAN button ingress or registry eligibility rule.
- Configuration SSE uses complete authoritative envelopes, idle comments, no event IDs and no
  replay buffer. Registration and its initial durable envelope are ordered atomically against
  replacement publication. Each subscriber has bounded pending output and cannot block publication.
- The simulated pad reaches the production FastAPI routes through a private in-process ASGI
  transport wrapped by production authentication middleware. It uses an ephemeral simulation
  certificate and fixed simulation identity without weakening the externally served app.
- The installed `httpx2.ASGITransport` buffers response bodies until completion and cannot carry an
  endless SSE response. The simulator drives the wrapped ASGI callable directly for its one stream
  and uses the finite-request transport for status and presses. Do not build a reusable transport.
- Direct button-pad transmission to vehicle CAN is deferred. This workflow adds no command mapping,
  firmware hook or generic extension for it.

## Ownership handoffs

Slice 1.5 owns the removed device transports, firmware, registry, effects and coordinator fields.
Return any incomplete prerequisite cleanup to that workflow rather than absorbing it here.

Workstream 1 owns the button scene model and projection. Workstream 2 owns principal shape and SAN
parsing. Workstream 3 owns database schema and direct repositories. Workstream 4 owns finite device
request models, route authorization and canonical input dispatch. Workstream 5 owns durable
synchronization, bounded subscriptions and lifecycle. Workstream 6 owns the configuration route,
authorization, nginx and generated OpenAPI artifacts. Workstream 7 owns the simulation-only client,
development tap seam and lifecycle composition.

Generated `protocol/openapi.json` and coordinator Hey API artifacts move with whichever route-owning
workstream changes their source. Do not hand-edit generated files.

## Whole-feature acceptance

- The independent-device work does not restore any generated custom protocol, coordinator-device
  ISO-TP, device registry/lifecycle, legacy firmware or project-device CAN simulation path removed
  by Slice 1.5.
- Vehicle CAN decoding, vehicle simulation and desired coordinator state remain intact.
- Button-pad and Servotronic certificates authenticate as role-bearing device principals; spoofed
  proxy headers and unknown roles do not.
- Only a button-pad device can use the implemented configuration, status and press behavior.
- The exact 16-button scene preserves active-only animation semantics and never contains a
  coordinator press-feedback overlay.
- Configuration and status persist directly in SQLite with the approved generation and receipt-time
  rules.
- A device receives the current complete configuration first, then immediate complete replacements;
  reconnect and restart do not manufacture generations.
- Slow or disconnected consumers cannot block the controller or grow memory without a bound.
- The simulated button pad validates the production envelope, reports its applied generation and
  submits one press through HTTP to the controller inbox exactly once.
- The coordinator OpenAPI document, generated Hey API artifacts, nginx configuration and current
  documentation agree with the implementation.
- Targeted checks and the final repository checks pass.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| 2026-09-18 | Treat the request to create this workflow as approval of Slice 02 despite its earlier draft label | Workflow creation requires an approved source, and the user explicitly requested conversion after Slice 01 completion | Aidan | All |
| 2026-09-18 | Make completed Slice 1.5 a prerequisite instead of repeating coordinator cleanup | Removal and simplification deserve their own implementation and review context | Aidan | All |
| 2026-09-18 | Give the button-pad scene its own workstream | It is the shared product contract for persistence, synchronization and simulation and does not belong to authentication or storage | Workflow author | 1-7 |
| 2026-09-18 | Use canonical certificate spellings directly in `DeviceRole` | Slice 1.5 removes the legacy protocol vocabulary and development device API | Workflow author from repository inspection | 2-7 |
| 2026-09-18 | Do not account for possible future button-pad vehicle-CAN transmission | It is speculative and needs a concrete vehicle command and safety contract before it affects firmware or APIs | Aidan | 1-7 |
| 2026-09-18 | Drive configuration SSE through a route-specific ASGI send/receive loop | The installed `httpx2.ASGITransport` buffers until response completion and deadlocks on an endless stream; a generic replacement is unnecessary | Workflow author from installed dependency inspection | 7 |
| 2026-09-18 | No external validation gate | The slice excludes hardware, nginx TLS and Wi-Fi proof; its production handlers and simulator can be exercised in process | Approved Slice 02 boundary | All |
