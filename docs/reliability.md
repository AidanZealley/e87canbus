# Reliability, health and service operation

`ControllerService` owns the process-local failure policy and bounded operational projection. Its
owner thread is the only controller mutation/effect path; HTTP, Socket.IO, CAN readers and device
adapters submit work without becoming alternate state owners.

## Failure policy

| Failure | Owner | Behavior |
|---|---|---|
| CAN reader failure | Controller runtime | Record the network fault, dispatch the safe fallback and terminate for supervisor restart when fatal. |
| Controller inbox overflow | Controller service | Latch one fault, reject new work, stop normal ingestion and dispatch the safe fallback without growing the queue. |
| Queue latency warning | Controller service | Preserve the ingress timestamp and expose current latency plus a warning while the configured threshold is exceeded. |
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
successful durable-storage initialization, a running controller owner and no fatal controller
fault. Publisher failures and browser disconnects remain transport concerns and do not make the
controller itself unready.

The fixed `controller.health` projection contains the opaque process boot ID, readiness and fatal
truth, explicit network/device/steering faults, bounded inbox depth/capacity/current latency and
overflow truth, persistence status, and publisher failure/drop/slow-client-isolation counters.
Network availability and selected device/capability state remain in the canonical `devices.state`
projection instead of being copied into health. Health is coalesced to at most 1 Hz. Per-event trace
detail is limited to 2,000 rows and publisher/client queues have fixed capacities.

Persistence, readiness and decision-useful publisher diagnostic changes commit a new global
revision and health topic revision even while controller input is idle. Those publisher changes
are running/fault transitions, publication failures, trace/resource drops and slow-peer queue
saturations; ordinary socket connections and trace subscription changes do not advance health.
Publisher-owned changes enter its one-slot health handoff directly, rather than calling the
publisher back through the service notification; failed `controller.health` delivery is diagnosed
but does not enqueue itself recursively.

Startup validates authority, initializes SQLite, starts the controller and readers, starts the
publisher, then marks ready. Shutdown reverses ownership deliberately: not-ready/reject, stop
ingress and commit safe state, stop publisher/socket tasks, then close adapters. Each thread and
task has one owner and a bounded join/cancellation check.

On physical Raspberry Pi deployments, `kcan`, `ptcan`, and `fcan` are boot-managed by dedicated
`systemd` units that apply their SocketCAN bitrates and raise the interfaces before the controller
starts. The controller requires all three units on physical installations, so a failed CAN bootstrap
also fails the controller start. Setup validates their SPI parents before starting the controller.
That keeps transport stable across reboot and makes device reconnects independent from any manual
bench script.

The console has an independent, smaller lifecycle. `e87canbus-console-kcan.service` raises only
`kcan` at 100 kbit/s with kernel listen-only mode before `e87canbus-console.service` starts. Its
health and complete `console.snapshot` report local CAN connection, frame activity and faults
without changing coordinator readiness or exposing raw frames. Coordinator or Ethernet failure
affects coordinator-backed console state but does not stop local K-CAN observation; console failure
does not affect coordinator control.

The canonical CLI exits nonzero for fatal controller termination, unexpected owner/timer/shutdown
failure, or failure to complete Uvicorn startup, allowing the bounded `systemd` restart policy to
act. Each role's same-origin frontend boundary falls back to its `index.html` only for client
routes. Missing assets and unknown `/api`, `/health` or Socket.IO paths remain real 404 responses.

For the canonical loopback, same-origin `systemd` deployment and operator commands, see
[coordinator and console operation](../deploy/README.md#routine-operation).
