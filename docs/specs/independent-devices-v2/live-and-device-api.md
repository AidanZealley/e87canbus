# Live and device API

- **Status:** Approved
- **Date:** 2026-09-16
- **Depends on:** [Architecture and boundaries](architecture-and-boundaries.md)

## Purpose

Define the SSE and HTTP contracts that replace Socket.IO and the coordinator-facing part of the
custom CAN protocol. This document specifies observable behavior. It leaves task boundaries and
internal class structure to later implementation planning.

## Common SSE behavior

An SSE endpoint returns `200`, `Content-Type: text/event-stream` and `Cache-Control: no-store`.
Nginx disables proxy buffering and uses a read timeout longer than the keepalive interval.

Each record contains one single-line JSON `data` field followed by a blank line. Hosts send an SSE
comment during idle periods so clients can detect a dead receive path:

```text
: keepalive

```

Streams do not send `id` fields and clients do not send `Last-Event-ID`. There is no replay buffer.
Every connection starts with a complete current value, so reconnection replaces replay.

Registering a subscriber and capturing its initial value form one operation. An update cannot fall
between them. Publication never waits on a client. Each client has bounded pending output; a client
that cannot keep up is disconnected and recovers from a fresh initial value.

Clients reconnect after an HTTP failure, read failure, idle timeout, or clean end of response. The
generated Hey API client's behavior must be verified for all four cases. A small application wrapper
owns any reconnect behavior the generated client does not provide.

## Coordinator browser stream

`GET /api/live` returns one stream to the coordinator or console browser. Each data record is a
discriminated union:

```json
{
  "type": "steering",
  "data": {
    "mode": "auto",
    "manual_assistance_level": 4
  }
}
```

The first record has type `snapshot` and contains every live projection the browser needs:

```json
{
  "type": "snapshot",
  "data": {
    "vehicle": {},
    "engine": {},
    "steering": {},
    "buttons": {},
    "health": {}
  }
}
```

Subsequent state records replace one complete projection. They are not patches. The initial event
also tells the frontend to reconcile its known durable TanStack Query roots. This catches resource
changes missed while disconnected.

Durable resource changes use the same stream:

```json
{
  "type": "resource.changed",
  "data": {
    "resource": "button_profile",
    "id": "profile-id",
    "revision": 3
  }
}
```

Live device registry state is not part of this contract. Device diagnostics come from ordinary admin
HTTP endpoints.

The live CAN trace, its subscription requests and its browser UI are removed. The simulation bus's
internal trace buffer remains available to tests.

## Console-host stream

The console host exposes its own `GET /api/live`. It sends a complete `console.snapshot` value on
connection and whenever its local CAN activity projection changes:

```json
{
  "type": "console.snapshot",
  "data": {
    "can": {}
  }
}
```

This is a separate OpenAPI document and a separate generated client. It does not import the
coordinator's live union merely because both use SSE.

## Device configuration stream

`GET /api/devices/configuration` requires an authenticated device certificate. Console and operator
principals cannot open it.

The coordinator selects a configuration by the certificate's device ID and selects its schema by
the certificate's role. The request contains neither value.

The first record is the current complete document. A changed desired configuration sends another
complete document immediately:

```json
{
  "generation": 42,
  "configuration": {
    "schema_version": 1,
    "buttons": []
  }
}
```

The OpenAPI response is the union of supported role envelopes. The configuration shapes are
structurally distinct. Firmware knows its compiled role and parses only that role's shape.

A device treats the newest document received on its current authenticated stream as authoritative,
even if its generation is equal to or lower than the stored generation. It validates the complete
envelope before applying it. If the complete envelope matches the stored value, it reports that
generation without rewriting the configuration partition.

The stream's keepalive is for the device's receive-path watchdog. If no bytes arrive before the
firmware's fixed timeout, it closes and reconnects the stream. This affects configuration freshness,
not the device's primary function and not coordinator-side presence.

## Device status

`POST /api/devices/status` requires an authenticated device certificate and returns `204`.

```json
{
  "status_version": 1,
  "applied_configuration_generation": 42,
  "configuration_error": null,
  "device": {}
}
```

The coordinator validates `device` against the authenticated role's status schema. A valid status
for another role is rejected. The body cannot name a device ID or role.

Devices post status:

- after boot;
- after applying or rejecting a configuration document; and
- when a meaningful role-specific status value changes.

They do not post heartbeats. The coordinator stores the value and receipt time as last reported
diagnostic information. It does not expire the value or derive online state from it.

The first button-pad status schema is an empty object. Its common fields carry everything required
for the first delivery. Servotronic later adds its own observed output and inhibit fields.

## Button presses

`POST /api/devices/button-pad/presses` accepts only a `button-pad` principal:

```json
{
  "button_index": 4
}
```

`button_index` is an integer from 0 through 15. The coordinator stamps receipt with its monotonic
clock, creates the existing canonical button-press input, and returns `204` once the input is
accepted.

Firmware sends one request for a physical press and does not retry an ambiguous request. Repeating a
toggle after a lost response could invert the driver's intent. Immediate visual feedback is local to
the pad and does not wait for the response.

## Authentication and authorization

Application authentication continues to trust certificate headers only from nginx on loopback.
Nginx verifies the client certificate against the installation CA. The application parses the one
URI SAN and checks the installation, canonical device ID and known role.

`PrincipalKind` gains one `DEVICE` member. The principal also carries its `DeviceRole`. Route
permissions admit device principals only to the configuration and status endpoints. The button
handler adds its stricter `button-pad` role check.

Simulation may inject the same verified-certificate headers from a trusted in-process or loopback
boundary. It must exercise the same certificate parsing, role authorization, request models and
handlers as hardware. This does not claim to simulate the nginx TLS handshake.

## Admin device diagnostics

`GET /api/devices` is operator-only and returns a generic list of devices that have authenticated
with the coordinator. Each item may contain:

- authenticated device ID and role;
- published and applied configuration generations;
- last reported status and its coordinator receipt time;
- current IP address and diagnostic hostname when available; and
- `on_wifi`, derived at request time from access-point association data.

`on_wifi` is `true` only while `wpa_supplicant` reports the station MAC as associated and `false`
when it does not. It is `null` when the host cannot read association state, so unavailable data is
not presented as offline. The adapter may join an associated MAC to the current dnsmasq lease to
obtain its address and hostname. A lease without a current association is not online.

This query belongs beside the controller rather than inside it. Device association never gates
commands, configuration writes or vehicle behavior. The admin frontend fetches it as server state;
it is not another live topic. Adding a role does not require a role-specific admin component.

The connected-devices view and CAN registry details are removed from the driving console.

## OpenAPI and generated clients

FastAPI request and response models are the editable contract source. The OpenAPI documents describe
the `text/event-stream` content with the actual event schema, not an empty media type beside an
`application/json` model.

Hey API remains the only browser client generator. It produces the HTTP and SSE operations,
TypeScript types, and Zod response validators. The implementation verifies that each streamed JSON
record runs through its generated validator.

The following bespoke machinery is removed:

- the Python live-event registries;
- both live JSON Schema files;
- both live-contract generator scripts;
- `json-schema-to-typescript` and its generated mappings;
- Socket.IO event maps and protocol-version constants; and
- Socket.IO and Engine.IO clients, servers and dependencies.

Generated files may be long. They are build products, not a second contract or authored application
layer. CI regenerates them and fails on drift.

## Failure behavior

- A malformed browser event fails validation visibly and reconnects from a fresh snapshot.
- An invalid device configuration leaves the last good value active and is reported in status.
- Loss of the device stream leaves the stored configuration active.
- Loss of a button request loses that press. Firmware does not replay it.
- A slow SSE consumer is disconnected rather than allowed to block publication or grow an
  unbounded queue.
- A host restart ends its streams. Clients reconnect and receive current complete values.
