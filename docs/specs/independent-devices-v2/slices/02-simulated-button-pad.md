# Slice 02: simulated independent button pad

- **Status:** Draft for approval
- **Depends on:** [Slice 01](01-browser-sse.md),
  [Live and device API](../live-and-device-api.md) and
  [First device delivery](../first-device-delivery.md)

## Outcome

A simulated button pad uses the production device API as an authenticated HTTPS client would. It
receives complete LED scenes, reports the generation it applied and sends button presses through the
real kernel input path. No project-device traffic is required on simulated CAN.

This slice introduces only the shared behavior demanded by the button pad. It does not build a
generic plugin system for hypothetical roles.

## Device identity and authorization

The application accepts the certificate roles `console`, `button-pad` and
`servotronic-controller`. A verified device certificate produces a `DEVICE` principal carrying its
canonical role and device ID. Certificate headers remain trusted only from nginx on loopback.

The device routes are closed by default. A supported device role may open its configuration stream
and post its status. Only a `button-pad` device may post to
`/api/devices/button-pad/presses`. Device IDs and roles never come from request bodies or query
parameters. Until Slice 06 adds the Servotronic document, a Servotronic principal authenticates but
cannot open a configuration stream or post role status.

Nginx exposes the device routes through the provisioned mutual-TLS network without exposing the
operator application to device principals.

## Button-pad configuration

The coordinator stores one complete configuration envelope per authenticated device ID. A new
button pad receives the scene derived from the active button profile and current application state.
Until assignment UI exists, all button pads use that one role default.

The envelope contains the durable generation and the button-pad document from the first-delivery
specification. Generations advance only when the desired complete document changes. A profile or
application-state change that changes the rendered scene publishes a replacement immediately.

Configuration storage and status storage use direct SQLite repositories. They do not introduce an
event log, cache layer or transport-neutral payload store.

## Simulated device

The simulated pad opens the production configuration handler through an in-process ASGI client. It
injects verified proxy headers at the trusted test boundary, then uses the same certificate parser,
authorization checks, request models and handlers as hardware.

It validates each envelope as the firmware will, records the applied generation and posts status.
A simulated press posts one button index and reaches the existing canonical button input exactly
once. It does not inject kernel events directly.

The simulator does not pretend to exercise nginx, TLS, flash persistence or physical CAN.

## Temporary boundary

The old simulated and physical custom-CAN button-pad paths may remain while this new client is
introduced. A composition selects one path; it never delivers the same press or scene through both.
The shared CAN registry and Servotronic transport remain untouched.

## Outside this slice

This slice does not build ESP32 firmware, add `e87ctl` firmware commands, expose admin diagnostics
or determine Wi-Fi presence.

## Acceptance

The slice is complete when:

- valid button-pad and Servotronic certificates authenticate as role-bearing device principals,
  while only the implemented button-pad role can use role-specific device behavior;
- console, operator and wrong-role principals cannot use button-pad device routes;
- a simulated button pad receives one complete initial scene;
- changing profile or application state sends the new scene without polling;
- active-only animations still resolve to a solid inactive track and authored active track;
- valid status is stored with its coordinator receipt time and no heartbeat is generated;
- one simulated press reaches the production kernel input once;
- an ambiguous button request is not retried;
- configuration generation survives coordinator restart and never advances for a reconnect; and
- the old CAN device paths still work in compositions that have not migrated.
