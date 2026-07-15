# Phase 7: Reliability, health and deployment

## Goal

Make the unified controller operationally robust through explicit failure policy, bounded
diagnostics, readiness, deterministic shutdown and one supervised Pi service. Demonstrate that web
or diagnostic failure cannot silently block vehicle processing.

This phase does not enable unverified physical outputs, add a distributed monitoring stack or hide
faults behind automatic retries.

## Preconditions

- Phases 1-6 are at least `Implemented`, with no unresolved state-ownership or public-contract
  blocker.
- Normal/peak simulated input and publication rates can be measured.
- Current setup/operator docs and scripts have been inventoried.

## Failure policy

Document and implement one explicit policy table owned by the controller service:

| Failure | Required behavior |
|---|---|
| CAN reader failure | Record network fault, request safe fallback and terminate/restart if fatal |
| Controller inbox overflow | Latch fault, stop normal ingestion, request safe fallback, never grow memory |
| Queue latency beyond warning | Record bounded diagnostic warning/counter; preserve ingress timestamp |
| CAN output failure | Record desired/output fault and apply evidence-backed fallback only |
| Steering actuator failure | Mark fatal and execute the defined software safe request; make no physical safe-state claim |
| SQLite read/write failure | Reject affected resource operation; preserve already loaded runtime operation where safe |
| Socket/publisher failure | Mark UI transport unhealthy; never block controller/effects |
| Slow socket/trace client | Coalesce/drop diagnostic/live intermediates; disconnect if required |
| Emulator failure | Report adapter fault through the same health projection without claiming physical behavior |
| Shutdown | Stop new commands, commit safe shutdown, close adapters and tasks in fixed order |

Automatic retries are allowed only where an operation is proven idempotent and bounded. Do not
retry unknown CAN output outcomes in a loop.

## Health model

Expose framework-independent health projections for:

- Controller lifecycle and boot ID.
- Each configured CAN network.
- Inbox capacity/overflow latch and latency warning state.
- Each selected custom-device adapter, using only supported evidence.
- Steering capability presence/fault.
- SQLite availability for durable operations.
- Live-state publisher status.
- Last fatal and non-fatal fault summaries.

Do not turn arbitrary log messages into public health states.

HTTP endpoints:

```text
GET /health/live
GET /health/ready
```

`live` proves the process/event loop responds. `ready` proves startup configuration, database load
and controller service reached its ready state. A browser/socket disconnect does not make the
controller itself unready.

## Bounded diagnostics

Track only useful bounded values:

- Current controller inbox depth and configured capacity.
- Maximum/rolling queue latency.
- Received/decoded/ignored/malformed frame counters by network.
- Effect sent/dropped/rate-limited/failed counters.
- Published/coalesced/dropped event counters by topic.
- Active socket and trace-subscriber counts.
- Current fixed trace-ring length/capacity.

Counters may be process-lifetime integers; retained per-event detail must remain bounded. Logs are
structured and high-frequency warnings are rate-limited.

Do not add Prometheus, OpenTelemetry or another service unless a separately approved operational
need appears. Health JSON and logs are sufficient for this roadmap.

## Startup and shutdown

Startup order:

1. Validate configuration and reject conflicting authorities/capabilities.
2. Initialize/migrate SQLite and load durable desired configuration.
3. Construct adapters with live TX absent unless explicitly evidence-granted.
4. Start controller owner and commit startup effects.
5. Start CAN readers/emulators/publisher.
6. Mark ready and accept commands.

Shutdown order:

1. Mark not ready and reject new commands.
2. Stop external ingress/readers.
3. Dispatch ordered shutdown and execute its effects.
4. Drain only explicitly bounded completion work; do not replay stale output.
5. Stop publisher/socket tasks.
6. Close adapters and database resources.

Every thread/task has one owner, stop signal and joined/cancelled verification.

## Service operation

Provide one `systemd` unit or repository template for the Pi that:

- Runs the canonical unified-controller command.
- Uses an explicit config/environment file path.
- Restarts on unexpected fatal exit with a bounded delay.
- Uses a working directory and user appropriate to repository deployment documentation.
- Sends logs to the journal.
- Does not grant CAN TX or device permissions beyond documented operator configuration.

Document installation, upgrade, restart, status and log commands. Do not bundle Chromium kiosk
startup unless separately requested.

The built frontend should be served same-origin by the application or an already-required simple
static boundary. Avoid adding a production reverse proxy only for architectural style.

## Security and exposure

Document the intended bind address and trust boundary. Development wildcard CORS or remote mutation
must not silently become the Pi production default. Authentication remains outside this roadmap
unless the selected non-loopback deployment requires a separate decision.

Development-only emulator actions must be absent or disabled in production composition.

## Reliability tests

- Reader failure, inbox overflow and actuator/output failure reach exact health/fallback paths.
- Socket and trace stalls cannot increase controller queue latency beyond the documented policy.
- SQLite outage rejects resources while live controller behavior remains as specified.
- Repeated startup/shutdown leaves no threads, tasks, sockets or file locks.
- Fatal exit is observable and suitable for `systemd` restart.
- Readiness transitions correctly around startup, fault and shutdown.
- All queues/rings expose and enforce their configured bounds.
- Development-only routes are unavailable in production composition.
- Live defaults remain RX-only after service installation.

## Soak and restart evidence

Run a backend/frontend simulated soak that includes telemetry, commands, resource reads, socket
reconnects and trace open/close. Record:

- Duration and generated input rates.
- Maximum controller inbox depth/latency.
- Publisher coalesced/dropped counts.
- Trace bounds and subscriber counts.
- Process memory trend after warm-up.
- Browser retained-state observations from Phase 5 metrics.
- Fault/health state at the end.

Exercise repeated service/controller restarts and confirm the frontend resynchronizes by boot ID and
durable settings/profiles survive.

## Completion criteria

- Every material failure has one documented and tested owner/policy.
- Health/readiness distinguish process, controller, adapters, persistence and UI transport.
- Diagnostics are sufficient to explain overload without retaining unbounded events.
- Startup/shutdown leave no orphaned resources.
- A canonical supervised Pi service and operator instructions exist.
- Production composition excludes development mutation routes and retains deny-by-default TX.
- Soak/restart evidence shows bounded backend and frontend state after warm-up.
- No new physical safety claim or unauthorized capability is introduced.

