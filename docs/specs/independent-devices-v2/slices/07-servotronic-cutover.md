# Slice 07: Servotronic firmware cutover

- **Status:** Draft, blocked by hardware evidence
- **Depends on:** [Slice 06](06-simulated-servotronic.md), the
  [selected board reference](../../../weact-can485-esp32.md) and the hardware evidence below

## Outcome

The physical ESP32 Servotronic controller owns speed observation, assistance calculation, output
control and failsafe behavior. It uses Wi-Fi only for configuration and status. Cutting it over
removes the final consumer of the repository-owned CAN device protocol.

This slice must not become an implementation workflow until its hardware evidence is recorded.

## Required hardware evidence

The repository must first contain:

- a named vehicle capture identifying the real speed frame, encoding, valid range and cadence;
- the selected CAN network and verified bitrate;
- the Servotronic actuator's voltage, current and polarity characteristics;
- the driver circuit, output pin and electrical safe state;
- current regulation or another justified bounded-output design;
- independent watchdog behavior and measured timeout;
- board power, fusing, grounding and transient-protection decisions; and
- bench evidence that the complete output stage reaches its safe state after firmware failure.

Community DBC labels and synthetic simulator IDs do not satisfy these gates.

## Firmware behavior after the gates are met

The firmware uses the selected WeAct board, shared partition contract and `e87ctl` provisioning
format. It restores its last valid Servotronic document and begins in the verified electrical safe
state before joining Wi-Fi.

It decodes speed directly from vehicle CAN and evaluates automatic assistance locally. Fixed mode
holds the configured `0.0` through `1.0` output without requiring speed. Invalid or stale speed
inhibits automatic mode. CAN faults, output faults and watchdog expiry produce the verified safe
state regardless of mode.

Configuration arrives through the role-authenticated device stream. Firmware applies and stores a
complete valid document atomically, reports status after meaningful changes and continues operating
through coordinator or Wi-Fi loss.

## Build and provisioning

`e87ctl firmware build servotronic-controller` builds a secret-free image for the same board.
`e87ctl provision servotronic-controller` issues the role certificate and flashes the common
partition layout. Role selection changes firmware and certificate role, not the board definition.

## Cutover and final deletion

After bench and installed-hardware verification, remove the remaining:

- CAN registry handshake and device catalogue;
- Servotronic ISO-TP curve and control transport;
- generated custom protocol source, outputs and checks;
- custom project arbitration-ID configuration;
- registry and transport state from diagnostics and simulation;
- shared ISO-TP library if no unrelated consumer remains; and
- tests, dependencies and documentation that describe those retired paths.

The vehicle CAN decoders and simulation CAN bus remain. CAN is still the vehicle transport.

## Outside this slice

This slice does not add network firmware update, configuration expiry, device-to-device control or
a CAN fallback for coordinator communication.

## Acceptance

The slice is complete when:

- every required hardware fact above has a repository-backed source or measurement;
- the physical controller starts and fails into the verified safe electrical state;
- automatic output matches the curve conformance cases using the captured speed signal;
- fixed mode applies the configured fraction, including maximum assistance at `1.0`;
- stale, invalid or missing speed inhibits automatic output within the measured bound;
- coordinator, Wi-Fi and firmware task failures trigger their specified local behavior;
- configuration and status use the production authenticated device API;
- power cycling offline restores the last accepted configuration;
- provisioning and reflashing preserve the identity and configuration rules; and
- no repository-owned CAN device protocol or consumer remains.

