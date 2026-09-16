# Live event transport

- **Status:** Proposed
- **Date:** 2026-09-16

## Goal

Replace Socket.IO with server-sent events as the one push transport from the coordinator to every
client, and from the console host to its own browser. Commands stay on HTTP.

This is the first of four workflows. It touches both hosts and both frontends and involves no
devices, so the transport is proven in a browser before any firmware depends on it.
[The device platform](device-platform.md) then builds on it, and
[device firmware provisioning](device-firmware-provisioning.md) follows.

## Why

Two reasons, and the second is why this happens now rather than later.

Socket.IO costs more than it returns here. It is a protocol over Engine.IO over WebSocket, with its
own handshake, packet framing, namespaces, acknowledgements and reconnection rules. The coordinator
already carries `hosts/src/e87canbus/adapters/socketio_server.py`, a bounded Engine.IO queue and a
slow-peer disconnect policy written to get backpressure the protocol does not provide.

Devices are about to become push clients. Implementing Engine.IO in C against mbedtls is a great
deal of code buying nothing, while an SSE reader on an ESP32 is a loop that accumulates lines until
a blank one. Choosing a transport the microcontrollers can speak, and then using it everywhere, is
cheaper than running two push mechanisms with two contracts, two reconnect behaviours and two sets
of connection handling.

## Two live channels, not one

`socketio_server.py` has two consumers and both migrate here, or the adapter and its dependencies
cannot be removed:

- the coordinator's live channel in `hosts/src/e87canbus/api/internal/live.py`, consumed by
  `frontend/packages/coordinator-client/src/live/`
- the console host's local live channel in `hosts/src/e87canbus/console/live.py` and `app.py`,
  consumed by `frontend/apps/console/src/local-live/`

They are separate contracts serving separate purposes and stay separate. Only the transport
underneath them is shared.

## Transport

**One stream per topic.** A stream is a resource, the same way an HTTP endpoint is, and it carries
one event type with one schema. There is no multiplexed channel and no event name on the wire.

The kernel already has the right seam. `StateTopic` in `hosts/src/e87canbus/kernel/commit.py` is a
closed enum of seven topics, and every commit already reports which of them changed. Each becomes
an endpoint, alongside the durable-resource invalidation signal:

```text
GET /api/live/vehicle
GET /api/live/engine
GET /api/live/steering
GET /api/live/buttons
GET /api/live/lighting
GET /api/live/devices
GET /api/live/health
GET /api/live/resources
```

A client issues an ordinary GET and the host replies `200` with `Content-Type: text/event-stream`
and `Cache-Control: no-store`, then holds the response open and writes records separated by blank
lines:

```text
data: {"mode":"manual","level":4}

: keepalive

data: {"mode":"auto","level":0}

```

Every `data` field is a single-line JSON document of that stream's one type. Multi-line `data` is
legal SSE and is not used here, so a device parser never has to join continuation lines. A line
beginning with `:` is a comment used as a keepalive. There are no `event:` fields, because a stream
carries one type, and no `id:` fields, because there is no replay.

Streams are shaped by `StateTopic`, not by what a particular screen needs. Consumer-shaped streams
would make the coordinator responsible for knowing what the console's car view puts on screen, and
`changed_topics` already gives the seam for free.

### This replaces multiplexing, deliberately

Socket.IO's native model is one connection carrying many named events, and an earlier draft of this
specification carried that shape onto SSE unexamined. It does not fit. OpenAPI 3.1 cannot express
"this stream carries these named events with these payloads", so a multiplexed stream can only be
described as a union, and the generated client discards the SSE `event:` field when it yields a
record. Keeping the union typed meant moving the event name into the JSON body, which is a
non-idiomatic wire format adopted to rescue a structure nothing required.

One stream per topic removes the whole problem, and three things get simpler rather than merely
more conventional:

- `controller.snapshot` and `ControllerSnapshotData` are deleted. They exist because a Socket.IO
  client needed one initial dump. Each stream's first event is that topic's snapshot.
- Coalescing stops being logic. A multiplexed client needs a queue plus a latest-value-per-topic
  rule keyed on the topic; a per-topic client needs a one-slot mailbox holding the latest value,
  with nothing to key on.
- A failure isolates to one topic instead of blanking the UI.

### HTTP/2 is a prerequisite

Browsers cap HTTP/1.1 at six connections per origin. Eight streams exhausts that and then blocks
ordinary API requests, which fails hard rather than slowly. `deploy/nginx/e87canbus.conf` currently
listens without HTTP/2, so this design does not work until it does.

Enabling it is one directive. Under HTTP/2 the streams multiplex over one TCP connection against a
default limit of around a hundred, nginx terminates HTTP/2 client-side and proxies HTTP/1.1
upstream unchanged, and uvicorn sees roughly eight connections per browser, which for asyncio is
nothing.

This is a prerequisite of the design rather than a tuning choice, and it is safe to depend on here
because the installation owns its nginx configuration and both browsers.

The cost beyond that is eight keepalives instead of one, which is bytes.

Devices are unaffected. `/api/devices/stream` was always one stream carrying one event type, so it
was already this shape.

## Every connection begins with a snapshot

A client that connects to a stream receives that topic's current value as the first record, then
live updates. There is no replay, no event ID, no `Last-Event-ID` handling and no retention policy.

This is possible because every live topic is already a complete value rather than a patch, which
ADR 0008 established, and because the frontend already reconciles durable HTTP resources after a
snapshot. A reconnecting client that receives the current state is in exactly the position replay
would have put it in.

Deleting replay removes the generation counter, the replay buffer, the retention policy, the
problem of distinguishing a stale event ID from the same number after a restart, and the race
between reading a snapshot and registering for updates. Earlier drafts of this specification
specified resume from `Last-Event-ID`; it was removed as machinery with no consumer.

Registering the client for updates and capturing the topic's current value must share one boundary,
so a change occurring between the two is neither lost nor delivered twice. Per-topic streams make
that boundary smaller: it now covers one value and one subscriber list rather than the whole
projection.

Values can skew across topics by the time between two connections opening. That is accepted. Each
topic's value is internally complete and the kernel remains its single owner, so the skew is a few
milliseconds of one dashboard reading fractionally newer than another, and it converges on the next
commit.

## The transport is one-way

With replay unnecessary and the trace removed, `client_to_server_event` has no members left and is
removed from the coordinator contract entirely. The push channel is one-way as a fact about the
system rather than a constraint SSE imposes on it.

Everything a client sends a host is an ordinary HTTP request with a response, status code and error
semantics. That is the split the system already uses for commands, and SSE does not disturb it.

## The live CAN trace is removed

The workbench's simulated CAN trace view is deleted rather than ported. It was useful while the
simulator was being built, and a bespoke feature-poor frame viewer is not worth carrying now that
dedicated CAN tools exist. Its subscribe and unsubscribe messages were the only reason the push
channel needed a client-to-server direction, and it was by far the most expensive thing the
coordinator published: up to a thousand frame rows a second against telemetry's small state objects
at 25 Hz.

Two different things share the name `trace`, and only one goes.

The **live trace publication** is removed: the deque, subscriber set, session tracking, batching and
drop counter in `hosts/src/e87canbus/api/internal/live.py`, `trace_hz` and `trace_batch_size` in
`LivePublicationConfig`, the three `auth.py` permission entries, and the contract models
`TraceSubscribeEvent`, `TraceUnsubscribeEvent`, `TraceBatchEvent`, `TraceRow` and `TraceBatchData`.
On the frontend that is `SimulatorTrace.tsx`, `can-trace-table/`, `frame-detail/` and
`live/trace-store.ts`, with their tests.

The **simulated bus trace buffer** in `hosts/src/e87canbus/runners/simulation/bus.py` stays, along
with `SimulatedCanTraceEntry`, `trace()`, `clear_trace()` and `SimulationConfig.trace_capacity`. It
is the simulation suite's observation point for which frames were transmitted, used throughout
`test_simulation_runtime.py` and `test_simulation_bus.py`. Removing it would gut those tests.

The simulated bus is in-process rather than a `vcan` interface, so after this no external tool can
observe simulated traffic either. That is accepted. If frame visibility is wanted again, bridging
the simulator onto a real `vcan0` gives candump and every other tool something to attach to, which
is better than what is being removed here.

## Authentication

The usual reason to reject SSE is that native `EventSource` cannot set request headers. It does not
apply twice over. Every client authenticates at the TLS layer anyway: the console through its
Chromium client certificate, operators through HTTP Basic, and devices through their provisioned
certificates. And the browsers do not use `EventSource`; the generated client reads the stream
through `fetch`, which can set headers.

Nginx keeps passing verified identity through `X-E87-Client-Verify` and `X-E87-Client-Certificate`
exactly as it does today, and the closed `HTTP_PERMISSIONS` table in
`hosts/src/e87canbus/api/auth.py` authorises each stream endpoint like any other route. There are
eight of them now rather than one, which is eight explicit table entries rather than a wildcard.

## Publication and fan-out

One producer serves several independent response bodies, so each connected client needs its own
state. A blocked client must not stop publication to the others, and TCP-level flow control does
not provide that on its own.

Keep the existing shape rather than replacing it: the controller thread stays separate from
publication, and publication keeps delivering the latest value rather than a backlog, so a slow
client receives current state. What changes is where the per-client state lives, and how little of
it there is.

Each subscriber to a topic holds a one-slot mailbox and a writer task. A new value replaces
whatever the slot holds, so a slow client skips intermediate values and receives the current one.
A client whose write blocks past a bounded timeout is dropped with its stream closed.

That is the whole of the backpressure policy. `SaturatingBoundedQueue` and `BoundedEngineIoServer`
existed to impose queue bounds and a slow-peer policy through Engine.IO, and the coalescing rule
they wrapped needed a key because one queue carried every topic. With one topic per stream, the
bound is one value and the key is gone.

### Typing

The transport swap must not open a hole in the contract, and today there is one. The last typed
step is `sio.emit(name, payload)`, whose signature is `(str, Any)`: nothing prevents emitting an
event name outside the contract or a payload that does not match one.

Per-topic streams close it without any new mechanism. Each stream route is a FastAPI endpoint
declaring one response model, exactly as every other route does, and the value it publishes is that
model. A publisher that produces the wrong type for a topic is a type error where it is written.

Serialise once per publication, not once per subscriber, so fan-out cost stays flat in client
count. The mailbox holds the encoded bytes and the writer task copies them.

There is no record envelope, no discriminant, no union and no mapped type on either side. That is
the point of the shape.

## Connection liveness

Hosts send a keepalive comment every fifteen seconds. It holds the connection open through idle
timeouts and gives every client bytes to time against.

Both client kinds can use it, which is a change from an earlier draft. That draft said browsers
could not count missed keepalives, which is true of native `EventSource` and not true of the
generated client: it reads the body through `fetch` and surfaces every record to `onSseEvent`,
including comment-only chunks that yield no data. So a browser can run the same idle watchdog an
embedded client runs, and neither has to rely on the platform noticing.

That matters because neither client detects a black-holed TCP connection without one. The reader
simply waits, and a dead link looks alive for minutes. The idle watchdog is the only thing that
finds it.

Reconnection is the client library's, with exponential backoff capped by `sseMaxRetryDelay`, and a
reconnect delivers a fresh snapshot. Embedded clients implement the same two rules by hand: a read
timeout and a reconnect.

Nginx needs `proxy_buffering off` and a long `proxy_read_timeout` on the stream locations in
`deploy/nginx/e87canbus.conf`, or events sit in a proxy buffer until it fills. One `location
/api/live/` block covers all eight. It also needs `http2 on`, for the reason given under Transport.
The `Upgrade` and `Connection` handling and the `map $http_upgrade` block exist only for WebSocket
and are removed.

## Contracts

The live channel has its own bespoke contract pipeline today, and it goes. Both channels move onto
the one the HTTP API already uses.

### What exists now

Four stages, none of which the HTTP API needs:

1. `api/models/live_contract.py` holds a closed tuple of `EventContract` pairing each event name
   with a Pydantic payload model.
2. `scripts/generate_live_contract.py` builds a union of `{event, args}` models and emits
   `protocol/live-events-v1.schema.json`.
3. `frontend/scripts/generate-live-contract.mjs` runs `json-schema-to-typescript` over it into
   `live-contract.gen.ts`, plus a `SocketEventMap` bridge turning each member into a handler
   signature.
4. `live-contract.type-test.ts` asserts the mapping, and `--check` modes fail CI on drift.

The console host has its own parallel copy of all four for its single event.

All of it exists to describe one connection carrying many named events. None of it is needed to
describe eight endpoints that each return one type.

It also produces compile-time types and nothing else. `openapi-ts.config.ts` generates `zod.gen.ts`
and `sdk.gen.ts` wires a `responseValidator` into every HTTP operation, so HTTP responses are
checked at runtime while live events are cast. The live channel has been the weaker of the two
contracts.

### What replaces it

Nothing new. Each stream route declares a `text/event-stream` response with its topic's model:

```python
responses={200: {"model": SteeringState, "content": {"text/event-stream": {}}}}
```

`@hey-api/openapi-ts` 0.99.0, already the pinned version, detects a `text/event-stream` response,
emits an SDK function returning `ServerSentEventsResult<SteeringState>`, and runs the generated Zod
validator on each parsed event before yielding it. The client consumes an async generator of one
type:

```ts
const { stream } = await streamSteering()
for await (const state of stream) {
  // typed and validated, generated from the same document as every HTTP type
}
```

This is the case the generator handles most plainly, which is why an earlier draft's spike is gone:
there is no union to express and no discriminant to rescue.

`generate_openapi.py` already post-processes the document, so there is a place for anything a route
declaration cannot express.

The console host publishes its own OpenAPI document and gets its own `openapi-ts` config. It has
two health routes and one stream, so this is small, and it is what lets the last of the bespoke
pipeline go.

### What this deletes

`scripts/generate_live_contract.py`, `scripts/generate_console_live_contract.py`,
`frontend/scripts/generate-live-contract.mjs`,
`frontend/apps/console/scripts/generate-live-contract.mjs`,
`protocol/live-events-v1.schema.json`, `protocol/console-live-v1.schema.json`, the
`json-schema-to-typescript` dependency, the `live:generate` and `live:check` scripts in three
`package.json` files, `live-contract.gen.ts`, `local-live/contract.gen.ts` and the `SocketEventMap`
bridge. `live-contract.type-test.ts` goes too: it asserts a hand-written mapping that no longer
exists.

`api/models/live_contract.py` goes as well. It is a closed registry of event names and payload
models, and with one model per route the routes are that registry. The payload models in
`api/models/live.py` stay, minus `ControllerSnapshotData`, which had no consumer once each stream
opens with its own value.

`protocol_version` has nothing left to version. The stream endpoints live in the OpenAPI document
alongside every other route and are versioned with it, so `PROTOCOL_VERSION`,
`CONSOLE_PROTOCOL_VERSION` and `LIVE_PROTOCOL_VERSION` go with the schemas they numbered.

### Payloads do not change

Apart from the trace deletion and the snapshot event, every surviving payload carries over
unchanged, including `DevicesState`, which changes later in the device platform work rather than
here. A failure during this change is then a transport or pipeline failure and not a payload one.

## Removal

The work is not complete while any of the following remains:

- `hosts/src/e87canbus/adapters/socketio_server.py`, including `SaturatingBoundedQueue`,
  `BoundedEngineIoServer` and `BoundedSocketIoServer`
- the `socketio.ASGIApp` mount and `app.state.socketio` in `hosts/src/e87canbus/api/main.py`
- `socketio` use in `hosts/src/e87canbus/console/app.py` and `console/live.py`
- the `python-socketio` and `python-engineio` dependencies, and the regenerated lock
- `socket.io-client` in `frontend/apps/console/package.json` and
  `frontend/packages/coordinator-client/package.json`, and the client code using it in both
  `coordinator-client/src/live/` and `console/src/local-live/`
- `ControllerResyncEvent`, made unnecessary by every connection beginning with a snapshot
- the live trace publication and its frontend panel, as listed above
- the `map $http_upgrade` block and `Upgrade` and `Connection` proxy headers in the nginx
  configuration
- the bespoke live contract pipeline in both hosts and both frontends, listed under Contracts

Do not leave a test asserting that Socket.IO or the trace view is absent. After removal,
`socketio`, `engineio`, `socket.io`, `Upgrade`, `resync`, `trace_subscribe`, `trace.batch`,
`trace_hz`, `json-schema-to-typescript`, `SocketEventMap`, `protocol_version` and
`controller.snapshot` must not appear outside this specification. `trace` still appears in the
simulation bus and its tests, which is correct.

## Verification

The existing live-contract tests for both channels carry over to the new transport and are the main
safety net. Add coverage only for what is genuinely new: snapshot on connect for both channels, the
snapshot and subscription boundary being atomic, keepalive emission, and a slow client being
dropped rather than buffered without limit.

The generated artifacts are checked the way the HTTP contract already is. `http:check` covers the
stream endpoints without extension, because they are ordinary routes in the same document, and a
stale OpenAPI document or generated client fails CI rather than being noticed in a browser.

Check by hand that a browser holds all eight streams at once. That is the assertion HTTP/2 is
carrying, and a misconfigured nginx fails it by blocking ordinary API requests rather than by
breaking a stream, which is not where anyone would look.

Check by hand on a provisioned pair that the coordinator UI and the console UI each recover from
their host restarting and from Wi-Fi loss without a manual reload, since automatic reconnection is
the behaviour being relied on and the browser, not the application, provides it.
