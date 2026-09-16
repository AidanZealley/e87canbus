# Live event transport

- **Status:** Proposed
- **Date:** 2026-09-16

## Goal

Replace Socket.IO with server-sent events as the one push transport from the coordinator to every
client. Commands stay on HTTP.

This is the first of four workflows. It touches the coordinator and both frontends and involves no
devices, so the transport is proven in a browser before any firmware depends on it.
[The device platform](device-platform.md) then builds on it, and
[device firmware provisioning](device-firmware-provisioning.md) follows.

## Why

Two reasons, and the second is why this happens now rather than later.

Socket.IO costs more than it returns here. It is a protocol over Engine.IO over WebSocket, with its
own handshake, packet framing, namespaces, acknowledgements and reconnection rules. The coordinator
already carries `hosts/src/e87canbus/adapters/socketio_server.py`, a bounded Engine.IO queue and a
slow-peer disconnect policy written to get backpressure that TCP provides for free. That file is
evidence of the protocol working against the requirement.

Devices are about to become push clients. Implementing Engine.IO in C against mbedtls is a great
deal of code buying nothing, while an SSE reader on an ESP32 is a loop that accumulates lines until
a blank one. Choosing a transport the microcontrollers can speak, and then using it everywhere, is
cheaper than running two push mechanisms with two contracts, two reconnect behaviours and two sets
of connection handling.

## Transport

The coordinator exposes one stream endpoint. A client issues an ordinary GET and the coordinator
replies `200` with `Content-Type: text/event-stream` and `Cache-Control: no-store`, then holds the
response open and writes records separated by blank lines:

```text
event: steering.state
id: 412
data: {"mode":"manual","level":4}

: keepalive

event: controller.snapshot
id: 413
data: {...}

```

`event` names the type, `data` carries one JSON document, `id` carries the monotonic event
generation, and a line beginning with `:` is a comment used as a keepalive.

Every `data` field is a single-line JSON document. Multi-line `data` is legal SSE and is not used
here, so a device parser never has to join continuation lines.

## Generations and resume

The coordinator maintains a monotonic generation counter and emits it as `id` on every event. A
reconnecting client sends `Last-Event-ID`, and the coordinator either resumes from that point or,
when it cannot, sends a complete current snapshot and continues. A client that has never connected
receives a snapshot first.

Because reconnection delivers a snapshot inherently, `ControllerResyncEvent` is removed rather than
ported. A client that wants current state closes the stream and reopens it.

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
`LivePublicationConfig`, the three `auth.py` permission entries, and the schema definitions
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
is better than what is being removed here. The simulated CAN layer is likely to be reconsidered on
its own terms before that matters.

## The transport is one-way

With resync unnecessary and trace subscription gone, `client_to_server_event` has no members left
and is removed from the contract entirely. The push channel is one-way as a fact about the system
rather than a constraint SSE imposes on it.

Everything a client sends the coordinator is an ordinary HTTP request with a response, status code
and error semantics. That is the split the system already uses for commands, and SSE does not
disturb it.

## Authentication

Native `EventSource` cannot set request headers, which is the usual reason to reject SSE. It does
not apply here, because every client authenticates at the TLS layer: the console through its
Chromium client certificate, operators through HTTP Basic, and devices through their provisioned
certificates. Nginx keeps passing verified identity through `X-E87-Client-Verify` and
`X-E87-Client-Certificate` exactly as it does today, and the closed `HTTP_PERMISSIONS` table in
`hosts/src/e87canbus/api/auth.py` authorises the stream endpoint like any other route.

## Connection handling

The coordinator sends a keepalive comment every fifteen seconds. A client treats two missed
keepalives as a dead connection and reconnects. Without this, a black-holed TCP connection looks
alive to both ends for minutes, which matters most on an embedded client with no user to notice.

Backpressure is the socket. A client that cannot keep up stops draining, the write blocks, and the
coordinator drops that stream after a bounded timeout. This replaces `SaturatingBoundedQueue` and
`BoundedEngineIoServer` rather than reimplementing them.

Nginx needs `proxy_buffering off` and a long `proxy_read_timeout` on the stream location in
`deploy/nginx/e87canbus.conf`, or events sit in a proxy buffer until it fills. The `Upgrade` and
`Connection` handling and the `map $http_upgrade` block exist only for WebSocket and are removed.

## Contract

Removing the client-to-server events and the trace is a breaking change, so
`protocol/live-events-v1.schema.json` becomes `live-events-v2` with `protocol_version` 2. The
generated console contract and the OpenAPI document regenerate with it. The schema loses
`client_to_server_event` entirely along with the trace definitions. Every remaining
`ServerToClientEvent` member carries over unchanged, including `DevicesStateEvent`, which changes
later in the device platform work rather than here.

Keeping the surviving payloads identical is deliberate. Apart from the trace deletion this change
swaps a transport and nothing else, so a failure during it is a transport failure and not a payload
one.

## Removal

The work is not complete while any of the following remains:

- `hosts/src/e87canbus/adapters/socketio_server.py`, including `SaturatingBoundedQueue`,
  `BoundedEngineIoServer` and `BoundedSocketIoServer`
- the `socketio.ASGIApp` mount and `app.state.socketio` in `hosts/src/e87canbus/api/main.py`
- the `python-socketio` and `python-engineio` dependencies
- `socket.io-client` in `frontend/apps/console/package.json` and
  `frontend/packages/coordinator-client/package.json`, and the client code using it
- the `map $http_upgrade` block and `Upgrade` and `Connection` proxy headers in the nginx
  configuration
- `live-events-v1.schema.json` and generated artifacts derived from it
- the live trace publication and its frontend panel, as listed above
- Socket.IO and Engine.IO references in `docs/reliability.md`, `frontend/README.md`, the root
  `README.md`, and any test asserting bounded-queue or slow-peer behaviour

Do not leave a test asserting that Socket.IO or the trace view is absent. After removal,
`socketio`, `engineio`, `socket.io`, `Upgrade`, `resync`, `trace_subscribe`, `trace.batch` and
`trace_hz` must not appear outside this specification. `trace` still appears in the simulation bus
and its tests, which is correct.

## Verification

The existing live-contract tests carry over to the new transport and are the main safety net. Add
coverage only for what is genuinely new: resume from `Last-Event-ID`, snapshot on first connect,
keepalive emission, and a slow client being dropped rather than buffered without limit.

Check by hand on a provisioned pair that the console recovers from a coordinator restart and from
Wi-Fi loss without a manual reload, since automatic reconnection is the behaviour being relied on
and the browser, not the application, provides it.
