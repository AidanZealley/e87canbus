# Slice 03: provisionable offline button pad

- **Status:** Draft for approval
- **Depends on:** [Slice 02](02-simulated-button-pad.md),
  [First device delivery](../first-device-delivery.md) and the
  [selected board reference](../../../weact-can485-esp32.md)

## Outcome

`e87ctl` builds and provisions an ESP32 button pad that performs its local behavior without Wi-Fi.
The physical pad renders a safe stored or compiled scene, scans buttons, provides immediate feedback
and receives K-CAN frames in listen-only mode.

This slice proves the board, flash layout, provisioning boundary and local firmware before network
behavior is added.

## Firmware project

The slice creates the ESP32 project under `devices/button-pad/`. Slice 1.5 already removed the old AVR
source and coordinator-facing CAN protocol, so this project starts from the independent JSON scene
and local hardware behavior.

The project uses the selected board's explicit 8 MB configuration and checked-in partition table.
Implement the small ESP32-side renderer directly from the approved scene schema. Slice 1.5 removes
the old AVR renderer; do not restore or wrap it as shared compatibility code.

Firmware starts button scanning and rendering before touching network identity. It restores one
strictly validated configuration envelope from `e87cfg`, falling back to a compiled safe scene. An
invalid stored value cannot partially replace that scene.

An assigned press flashes locally. An unassigned press does nothing. This slice has no remote press
delivery or coordinator-driven feedback.

## CAN readiness

TWAI uses GPIO26 and GPIO27 at 100 kbit/s in listen-only mode. A bounded loop drains valid standard
frames. It does not decode them, retain a trace or change LED behavior from their contents.

A bench CAN source proves reception. The firmware never queues or transmits a CAN frame. Automatic
headlight dimming remains deferred until a named capture defines the real signal and cadence.

## Build and provisioning

`e87ctl` implements:

```text
uv run e87ctl firmware build button-pad
uv run e87ctl provision button-pad --firmware <manifest> --port <serial>
```

The build command invokes PlatformIO and emits the secret-free manifest and flash images specified
by the first-delivery document. The standalone `e87ctl` package owns its small table of supported
firmware targets and certificate roles. It does not import the host package.

Provisioning verifies the manifest, connected chip and flash size before writing. It warns that the
microSD card must be removed. It generates a fresh device ID, key, certificate and `e87id` image from
the installation recovery package, then flashes all images in one operator-confirmed operation.

An ordinary firmware reflash leaves `e87id` and `e87cfg` untouched. Full provisioning replaces
identity and clears configuration.

## Hardware facts recorded during the slice

The button-pad README records the physical PCB revision, NeoTrellis I2C pins, logical-to-physical
button map, measured safe brightness ceiling and bench wiring. These values come from the assembled
hardware rather than a guessed pin assignment.

## Outside this slice

Firmware does not join Wi-Fi, open SSE, post status or send button requests. It does not decode a
BMW CAN signal. Network firmware update and use of the microSD card remain out of scope.

## Acceptance

The slice is complete when:

- one build artifact can be verified and flashed more than once;
- the manifest rejects a wrong chip, wrong flash size, overlap, changed digest or out-of-range image;
- full provisioning creates a certificate accepted by the coordinator parser from Slice 02;
- firmware reflash preserves identity and configuration partitions;
- full provisioning replaces identity and clears configuration;
- the physical pad boots to a safe scene without Wi-Fi;
- power cycling restores a valid stored scene and rejects an invalid one;
- assigned and unassigned buttons have the specified local behavior;
- injected 100 kbit/s standard frames are received without affecting LEDs;
- the board transmits no CAN frames; and
- the old AVR upload path and source-only dependencies made unusable by the firmware replacement
  are removed.
