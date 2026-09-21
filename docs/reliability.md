# Reliability, health and service operation

`ControllerService` owns the process-local failure policy and bounded operational projection. Its
owner thread is the only controller mutation/effect path; HTTP, SSE publication, CAN readers and
device adapters submit work without becoming alternate state owners.

## Failure policy

| Failure | Owner | Behavior |
|---|---|---|
| CAN reader failure | Controller runtime | Record the network fault, dispatch the safe fallback and terminate for supervisor restart when fatal. |
| Controller inbox overflow | Controller service | Latch one fault, reject new work, stop normal ingestion and dispatch the safe fallback without growing the queue. |
| Queue latency warning | Controller service | Preserve the ingress timestamp and expose current latency plus a warning while the configured threshold is exceeded. |
| CAN output failure | Effect executor/controller runtime | Record desired/output fault, dispatch the configured fallback once and terminate for supervisor restart. An unknown send result is never retried; software does not prove a physical safe state. |
| Steering actuator failure | Controller runtime | Mark fatal and execute the software safe request; do not claim a physical safe state. |
| SQLite read/write failure | Resource repository/API | Reject that resource operation, mark persistence unavailable and preserve already-loaded runtime operation where safe. |
| SSE publisher failure | Live-state publisher | End affected requests without blocking or recursively notifying the controller owner. |
| Slow SSE subscriber | Live-state publisher | Coalesce projection intermediates, bound pending records and disconnect the saturated request. |
| Emulator failure | Simulation runtime | Detach the failed emulator and report a typed adapter fault without claiming physical behavior. |
| Shutdown | Controller service/lifespan | Reject commands, stop ingress, commit the safe request, drain bounded completion, stop publication, close adapters and verify owned threads/tasks stop. |

Automatic retry is limited to bounded operations with known idempotence. CAN sends with an unknown
outcome are dropped and diagnosed, never replayed in a retry loop.

## Health and bounds

`GET /health/live` proves the ASGI process responds. `GET /health/ready` additionally requires
successful durable-storage initialization, a running controller owner and no fatal controller
fault. Publisher failures and browser disconnects remain transport concerns and do not make the
controller itself unready.

The `health` SSE projection contains readiness and fatal truth, explicit network, device and
steering faults, bounded inbox depth, capacity and current latency, overflow truth, and persistence
status. Health is coalesced to at most 1 Hz. The internal simulation trace remains limited to 2,000
rows for backend tests. Each SSE subscriber has a fixed pending-record capacity, and saturation
cancels that request.

Startup validates authority, initializes SQLite, starts the controller and readers, starts the
publisher, then marks ready. Shutdown reverses ownership deliberately: not-ready/reject, stop
ingress and commit safe state, stop SSE publisher tasks, then close adapters. Each thread and
task has one owner and a bounded join/cancellation check.

On physical Raspberry Pi deployments, `kcan`, `ptcan`, and `fcan` are boot-managed by dedicated
`systemd` units that apply their SocketCAN bitrates and raise the interfaces before the controller
starts. The controller requires all three units on physical installations, so a failed CAN bootstrap
also fails the controller start. The provisioned image fixes their SPI assignments, and the
physical checkpoint validates those parents before release acceptance. That keeps transport stable
across reboot and makes device reconnects independent from any manual bench script.

The console has an independent, smaller lifecycle. `e87canbus-console-kcan.service` raises only
`kcan` at 100 kbit/s before `e87canbus-console.service` starts. The car console profile uses kernel
listen-only mode; the bench profile permits ACKs without granting application transmission. Its
health and complete `console.snapshot` report local CAN connection, frame activity and faults
without changing coordinator readiness or exposing raw frames. Coordinator or Wi-Fi failure
affects coordinator-backed console state but does not stop local K-CAN observation. Console failure
does not affect coordinator control.

The canonical CLI exits nonzero for fatal controller termination, unexpected owner/timer/shutdown
failure, or failure to complete Uvicorn startup, allowing the bounded `systemd` restart policy to
act. Each role's same-origin frontend boundary falls back to its `index.html` only for client
routes. Missing assets and unknown `/api` or `/health` paths remain real 404 responses.

## Abrupt power loss

Both Pis can lose power without warning, so SD card writes during normal operation are kept to a
minimum. The kiosk's Chromium profile and disk cache live on the unit's tmpfs `RuntimeDirectory`,
which leaves the installation CA in the kiosk user's `~/.pki/nssdb` as the only browser state on
the card. Deliberate writes to `application.sqlite3` remain the controller's own exposure.

The systemd journal keeps its distribution default so that hardware bring-up retains post-drive
logs. Moving it to `Storage=volatile` would remove the remaining routine write traffic and is worth
revisiting once the vehicle installation is settled. Card replacement is provisioned from the
recovery package, so a corrupt card costs a reprovision rather than a rebuild.

For the canonical provisioned hosts, authenticated network and operator access, see the
[coordinator and console provisioning runbook](../deploy/README.md).
