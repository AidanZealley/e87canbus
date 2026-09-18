# First device delivery: button pad

- **Status:** Approved
- **Date:** 2026-09-16
- **Depends on:** [Architecture and boundaries](architecture-and-boundaries.md) and
  [Live and device API](live-and-device-api.md)

## Purpose

Deliver one real independent device end to end. The button pad is first because it can prove
firmware build, provisioning, authentication, configuration push, device input and vehicle CAN
readiness without adding a vehicle actuator.

This document describes the completed button-pad result. Later planning divides it into vertical
slices that always leave the repository in a coherent state.

## Prerequisite

The selected hardware is the
[WeAct CAN485 ESP32 device board](../../weact-can485-esp32.md). The vendor specifies an
ESP32-D0WD-V3 with 8 MB flash, which fixes the build target and partition contract. `e87ctl` still
checks the connected chip and detected flash size before writing it.

The repository has no capture-backed headlight signal. The first delivery therefore proves CAN
reception without interpreting a vehicle frame. Headlight-driven dimming is deferred until a later
capture supplies the arbitration ID, payload encoding and cadence.

## Button-pad behavior

The replacement firmware targets the confirmed ESP32 board and becomes the live project under
`devices/button-pad/`. It is not a port of the AVR CAN state machine.

At boot it:

1. Initializes button scanning and LEDs without waiting for Wi-Fi.
2. Restores the last valid configuration from its configuration partition, or uses its compiled
   default.
3. Starts its listen-only K-CAN receive path, renders that scene and accepts local button input.
4. Validates its provisioned identity, joins Wi-Fi and opens the configuration stream.
5. Posts its status after the network path is available.

Losing Wi-Fi or the coordinator does not clear the scene or stop button scanning. Assigned buttons
still show immediate local feedback. Their HTTP requests fail once and are not retried.

The device configures TWAI for K-CAN at 100 kbit/s in listen-only mode. A bounded receive loop drains
valid standard frames without transmitting, decoding or retaining an unbounded trace. Bench tests
prove reception with injected frames. No CAN frame changes button-pad behavior in this delivery.

## Configuration document

The coordinator resolves the active button profile and current application state into the exact
scene the pad should render. The device knows whether a button is assigned, its resolved RGB colour,
and an optional animation. It does not know button commands, steering modes, profile IDs or other
devices.

```json
{
  "schema_version": 1,
  "brightness": 255,
  "buttons": [
    {
      "assigned": true,
      "colour": [0, 0, 255],
      "animation": {
        "type": "breathe",
        "period_ms": 2000,
        "minimum": 8,
        "maximum": 255
      }
    },
    {
      "assigned": false,
      "colour": [0, 0, 0],
      "animation": null
    }
  ]
}
```

`brightness` is an integer from 0 through 255. It scales the complete rendered output, including
animations and local press feedback, without altering the stored button tracks. Firmware also
enforces the separately verified physical current limit.

`buttons` contains exactly 16 entries in physical button order. RGB channels and animation
brightness values are integers from 0 through 255.

Supported animation values are `{"type":"breathe","period_ms":2000,"minimum":8,"maximum":255}`
and `{"type":"blink","on_ms":100,"off_ms":100}`.

The existing authoring bounds remain: breathe periods are 250 through 10,000 ms; blink durations
are 1 through 10,000 ms; and a breathe minimum cannot exceed its maximum. A null animation means a
solid colour.

Firmware validates the version, entry count, every field and every bound before replacing the active
scene. Unknown fields, versions or animation types reject the complete document. The last valid
scene remains active and status records the error.

The coordinator sends a new complete scene whenever the active profile or application state changes
what the pad should display. It resolves inactive brightness and active state before sending. The
pad renders the supplied scene rather than reimplementing coordinator application rules.

The existing profile authoring behavior remains. An authored animation applies only while its
command is active. When maximum assistance is inactive, for example, the coordinator sends that
button's dim solid appearance. When maximum assistance becomes active, it replaces the scene with
the authored blink track. The device contract carries the currently resolved track, so it does not
need separate active and inactive programs or knowledge of the command condition.

An unassigned button does not send a request or flash. An assigned button flashes its current colour
immediately when pressed, then sends its index once. Any later state change arrives as a replacement
configuration document. There is no coordinator-driven feedback or overlay command.

## Coordinator behavior

The coordinator stores a button-pad configuration envelope for each authenticated device ID. Until
a device-specific assignment UI exists, every button pad receives the scene derived from the one
active button profile. A new device ID receives that role default on first connection.

Button presses use the production HTTP handler and existing single-owner kernel input. The active
profile remains the authority for what an index means. Firmware never carries the command binding.

The simulated button pad becomes a client of the same configuration, status and button endpoints.
It may use an in-process ASGI transport, but it passes through the production request models,
authentication parsing, role checks and kernel input path.

The driving console loses its connected-devices view. The admin application's generic device query
shows the button pad after its first authenticated contact and reports Wi-Fi association separately
from its last status.

## Firmware build

`e87ctl` adds:

```text
uv run e87ctl firmware build button-pad
uv run e87ctl provision button-pad --firmware <manifest> --port <serial>
```

Use PlatformIO's `ESP32 Dev Module` target with an explicit 8 MB flash setting and the checked-in
partition table. The command invokes the checked-in build project; it does not duplicate the
firmware build system in Python.

The build produces a secret-free manifest and every image required for a physical flash. Each flash
entry names its file, offset, byte length and SHA-256 digest. The manifest also records:

- format version and device target;
- chip and build environment;
- build time, Git commit and dirty flag;
- provisioning interface version; and
- the identity-partition offset and maximum size.

`e87ctl` validates every field, digest, length, overlap and flash bound before invoking `esptool`.
The chip reported by the connected board must match the manifest.

The `e87ctl` device table owns its provisionable target names and certificate-role strings. The
standalone `e87ctl` package does not import `e87canbus`. Integration tests prove that certificates it
creates are accepted by the coordinator's authentication code.

## Flash regions

Both the button pad and Servotronic controller use the 8 MB partition table recorded in the
[board reference](../../weact-can485-esp32.md#internal-flash-layout). It contains:

- ordinary ESP-IDF NVS for firmware runtime data;
- OTA metadata and two application slots, with no network update implementation;
- `e87id`, a dedicated NVS identity partition; and
- `e87cfg`, a dedicated NVS configuration partition.

The two application slots reserve a future physical constraint. The firmware runs from the first and
does not write the second during this work.

`e87cfg` stores the accepted configuration envelope as one NVS value. NVS commit supplies atomicity
and wear levelling. An identical document does not cause another flash write.

## Provisioned identity

At flash time `e87ctl` issues a P-256 client key and certificate from the existing installation
recovery package. It generates the `e87id` NVS image and writes it in the same verified flash
operation as the firmware.

The identity partition contains:

- format version;
- Wi-Fi SSID and password;
- installation CA certificate;
- device private key and certificate; and
- the certificate issue time as the initial TLS clock floor.

It contains no application configuration, network address or separate copy of the role and device
ID. Firmware reads those from the certificate SAN. It derives its DHCP hostname from them.

An ESP32 has no trustworthy wall clock after power loss. Before its first TLS connection, firmware
sets its validation clock to the provisioned floor. After an authenticated coordinator response it
advances and persists that floor from the response date. The stored floor never moves backwards.
This is TLS bootstrap state, not a clock used for button events.

Firmware validates the identity format, key and certificate parsing, role, and URI SAN before
starting Wi-Fi. The TLS handshake validates the coordinator certificate against the provisioned CA
and fixed address. A missing or invalid identity prevents network access but does not prevent local
button-pad operation.

Reflashing firmware writes neither `e87id` nor `e87cfg`. Full provisioning replaces `e87id` and
clears `e87cfg`, because a new identity must not boot with configuration assigned to the old device
ID.

## Migration and removal

The new firmware and HTTPS path are proven before the button pad's custom CAN path is removed. The
repository may temporarily contain the new button-pad path beside the old Servotronic protocol.

After button-pad cutover, remove button-pad-specific registry messages, routing, effects, codecs,
generated constants, simulator controls, frontend fields and tests that no longer have a consumer.
Keep shared registry or ISO-TP machinery only while Servotronic still uses it. Do not retain a
button-pad compatibility path or fallback.

The AVR project is replaced by the ESP32 project in `devices/button-pad/`. Git retains the old
implementation; the live tree does not need a second compilable reference copy. The independently
tested button-pad effect renderer may be reused if it fits the new firmware cleanly, otherwise the
replacement owns an equivalent small renderer and the unused library is deleted.

The coordinator-panel firmware and upload script are unrelated and remain unchanged.

## Acceptance

The first delivery is complete when:

- a firmware artifact built once can be verified, provisioned and flashed to the confirmed board;
- the pad boots and renders a safe scene without Wi-Fi or stored configuration;
- its listen-only K-CAN path receives injected standard frames at 100 kbit/s and transmits none;
- arbitrary received CAN payloads do not alter button-pad behavior;
- a provisioned pad joins the existing access point and authenticates to the coordinator;
- it receives and atomically stores its current configuration;
- a profile or application-state change updates the physical pad without polling;
- a physical press reaches the real kernel input path once and receives immediate local feedback;
- power cycling without the coordinator restores the last accepted scene;
- invalid configuration leaves the last good scene active and appears in last reported status;
- the simulated pad exercises the same coordinator API behavior; and
- the old button-pad CAN path and every consumer made dead by the cutover are removed.

Servotronic migration and final deletion of the shared custom CAN protocol may be separate vertical
slices. They are not required to claim that the first independent device works. Browser Socket.IO
was removed by [ADR 0017](../../decisions/0017-browser-live-state-over-sse.md).
