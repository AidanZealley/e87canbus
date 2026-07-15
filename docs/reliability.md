# Reliability, health and service operation

`ControllerService` owns the process-local failure policy and bounded operational projection. Its
owner thread is the only controller mutation/effect path; HTTP, Socket.IO, CAN readers and device
adapters submit work without becoming alternate state owners.

## Failure policy

| Failure | Owner | Behavior |
|---|---|---|
| CAN reader failure | Controller runtime | Record the network fault, dispatch the safe fallback and terminate for supervisor restart when fatal. |
| Controller inbox overflow | Controller service | Latch one fault, reject new work, stop normal ingestion and dispatch the safe fallback without growing the queue. |
| Queue latency warning | Controller service | Preserve the ingress timestamp and retain only current/maximum latency plus a logarithmically rate-limited warning counter. |
| CAN output failure | Effect executor/controller runtime | Record desired/output fault, dispatch the configured fallback once and terminate for supervisor restart. An unknown send result is never retried; software does not prove a physical safe state. |
| Steering actuator failure | Controller runtime | Mark fatal and execute the software safe request; do not claim a physical safe state. |
| SQLite read/write failure | Resource repository/API | Reject that resource operation, mark persistence unavailable and preserve already-loaded runtime operation where safe. |
| Publisher or socket failure | Live-state publisher | Mark UI transport unhealthy without blocking or recursively notifying the controller owner. |
| Slow socket or trace client | Live-state publisher | Coalesce live intermediates, bound trace/event queues and disconnect a peer whose fixed Engine.IO queue saturates. |
| Emulator failure | Simulation runtime | Detach the failed emulator and report a typed adapter fault without claiming physical behavior. |
| Shutdown | Controller service/lifespan | Reject commands, stop ingress, commit the safe request, drain bounded completion, stop publication, close adapters and verify owned threads/tasks stop. |

Automatic retry is limited to bounded operations with known idempotence. CAN sends with an unknown
outcome are dropped and diagnosed, never replayed in a retry loop.

## Health and bounds

`GET /health/live` proves the ASGI process responds. `GET /health/ready` additionally requires
successful durable-storage initialization, a running controller owner, started publication and no
fatal controller fault. A browser disconnect is a publisher/client concern and does not make the
controller itself unready.

The fixed `controller.health` projection contains the opaque process boot ID; lifecycle/readiness;
per-network connection, fault, frame and effect counters; bounded inbox depth/capacity and latency;
selected device and steering evidence; persistence status; publisher/event counters; active socket
and trace-subscriber counts; trace-ring length/capacity; and last fatal/non-fatal summaries. It is
coalesced to at most 1 Hz. Counters may grow for the process lifetime, but per-event trace detail is
limited to 2,000 rows and publisher/client queues have fixed capacities.

Persistence, readiness and publisher/socket-only changes commit a new global revision and health
topic revision even while controller input is idle. Publisher-owned changes enter its one-slot
health handoff directly, rather than calling the publisher back through the service notification;
failed `controller.health` delivery is diagnosed but does not enqueue itself recursively.

Startup validates authority, initializes SQLite, starts the controller and readers, starts the
publisher, then marks ready. Shutdown reverses ownership deliberately: not-ready/reject, stop
ingress and commit safe state, stop publisher/socket tasks, then close adapters. Each thread and
task has one owner and a bounded join/cancellation check.

The canonical CLI exits nonzero for fatal controller termination, unexpected owner/timer/shutdown
failure, or failure to complete Uvicorn startup, allowing the bounded `systemd` restart policy to
act. The same-origin frontend boundary falls back to `index.html` only for client routes such as
`/dev` and `/car`; missing assets and unknown `/api`, `/health` or `/socket.io` paths remain real
404 responses.

## Soak and restart evidence — 2026-07-15

The T3 browser ran the development frontend against isolated simulated backends and a temporary
SQLite database for more than 13 minutes through a deliberate backend restart. Two 42-second
generated windows each sent 600 telemetry commands (14.3 commands/s), interleaved 30
settings/profile read pairs, and the second window added 100 alternating semantic steering
commands. Trace was opened, closed by route navigation, reopened, and exercised across reconnect.

- The controller inbox stayed within depth 1 of 1,024; maximum observed queue latency was 1.920 ms,
  with no warning or overflow latch.
- Final publisher diagnostics reported zero publication failures, drops or transport saturations.
  Health intermediates were coalesced (2,228 at the sampled point), the trace ring remained within
  1 of 2,000 at that point, and trace subscribers moved exactly 1 → 0 → 1 with route ownership.
- The replacement backend reported 2,305 received/decoded F-CAN frames, no malformed/ignored
  frames, 41 sent and 59 rate-limited K-CAN effects, and 2,120 successful simulated steering
  effects with no failures.
- Backend RSS was 55.1 MB during warm-up, fell to 39.6 MB and was 42.3 MB after 3 minutes 39 seconds;
  the preceding process was 39.7 MB after 4 minutes 35 seconds. Browser heap observations moved
  from 61.3 MB through 50.7 MB to 53.0 MB, with 777 DOM nodes and 25 rendered virtual trace rows
  after reopening the trace.
- The browser replaced state on the new boot ID, returned to `Connected`, retained no
  `Reconnecting` badge, and durable settings revision 2 (`kmh`) survived the backend restart.
  A discovered trace re-subscription omission was fixed so an open trace owner subscribes again on
  every transport connection epoch; a transport regression test covers it.
- Final liveness/readiness were both HTTP 200; controller health was ready and non-fatal, with no
  fatal/non-fatal fault summary. The user's longer-running application tabs also remained stable
  well beyond the former 5–10 minute crash window.

This is simulated software evidence only. Real CAN TX and physical steering output were not enabled,
and no physical safe-state or vehicle behavior is claimed.

For the canonical loopback, same-origin `systemd` deployment and operator commands, see
[Pi controller operation](../deploy/README.md).
