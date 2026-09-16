# Slice 04: networked button-pad cutover

- **Status:** Draft for approval
- **Depends on:** [Slice 02](02-simulated-button-pad.md) and
  [Slice 03](03-provisionable-offline-button-pad.md)

## Outcome

The physical ESP32 button pad becomes the live device. It joins the provisioned Wi-Fi network,
authenticates with its device certificate, receives current configuration immediately and submits
status and button presses over HTTPS. Its repository-owned custom CAN path is deleted.

## Network startup

Local button and LED behavior starts before network work. Firmware validates `e87id`, derives its
role, device ID and DHCP hostname from the certificate, then joins Wi-Fi and connects only to the
coordinator at `10.42.0.1`.

The certificate issue time supplies the initial TLS validation floor. A successfully authenticated
coordinator response may advance and persist that floor from its HTTP date. It never moves
backwards.

Invalid identity prevents network access but does not stop local button or LED behavior.

## Configuration client

Firmware opens `GET /api/devices/configuration`, consumes the initial complete envelope and
reconnects after every failure or termination described by the live API specification. Keepalive
comments reset only the receive-path watchdog.

The firmware strictly validates the complete role document before changing the active scene. It
commits the accepted envelope to `e87cfg`, skips an identical write and reports the applied
generation. Losing the stream leaves the stored scene active.

## Device requests

Firmware posts status after network startup and after applying or rejecting configuration. The
button-pad role-specific status object is empty in this slice.

An assigned physical press receives immediate local feedback and produces one request to
`POST /api/devices/button-pad/presses`. Firmware does not retry an ambiguous request. An unassigned
button sends nothing.

## Cutover and removal

After the physical path passes end-to-end verification, remove every button-pad-only consumer of:

- CAN button events and incremental LED effects;
- button-pad registry frames and registry projection fields;
- button-pad ISO-TP configuration transfer;
- generated custom constants, codecs and test vectors with no remaining consumer;
- simulator controls that inject the retired button-pad CAN messages; and
- host tests and documentation that describe the removed path.

Keep registry, ISO-TP and generated protocol machinery still used by Servotronic. Do not leave a
button-pad fallback, feature flag or compatibility facade.

## Outside this slice

This slice does not add headlight decoding, admin network-presence UI, Servotronic migration or
network firmware update.

## Acceptance

The slice is complete when:

- a provisioned physical pad authenticates to the coordinator over mutual TLS;
- it receives and stores the current scene after first connection;
- a profile or application-state change updates it without polling;
- active-only animation behavior matches the coordinator preview;
- a press reaches the production kernel once and local feedback does not wait for the request;
- loss of Wi-Fi or coordinator leaves local scanning, rendering and CAN reception running;
- power cycling offline restores the last accepted scene;
- invalid configuration leaves the last good scene active and appears in status;
- reconnecting after clean EOF and transport failures converges on current configuration;
- the simulated client still exercises the same coordinator handlers; and
- no button-pad custom CAN consumer remains in the live tree.

