# Phase 1 — Specification and protocol

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Agent prompt](phase-agent-prompt.md) · Previous: none ·
[Next phase](phase-2-kernel-registry-and-gating.md)

## 1. Objective

Establish the final terminology, configuration/domain vocabulary, byte-level
CAN protocol, generated artifacts, and conformance vectors before runtime
behavior depends on them.

## 2. Dependencies and starting state

- No earlier registry phase is required.
- The existing source of truth is `protocol/custom.toml`, with a generator that
  currently understands only button events and LED snapshots.
- `DeviceRole` currently contains only `button_pad` and the broad
  `DeviceProjection` mixes desired and observed LED state.
- The placeholder device directory and several runtime symbols still use
  “steering controller”.
- Read ADRs 0004, 0005, 0006, and 0008 before changing protocol boundaries.

## 3. In scope

- Rename optional hardware terminology to `servotronic_controller`.
- Add the six registry message definitions at `0x702`–`0x707`.
- Generalize generated protocol artifacts without hand-copying constants.
- Add strict Python codecs and fixed conformance vectors.
- Add the static catalogue, identity, source, and lifecycle domain types.
- Prepare removal of duplicate LED truth.
- Update protocol and design documentation.

## 4. Explicitly out of scope

- Runtime registry transitions or timers.
- Feature gating.
- Socket.IO schema migration.
- Virtual registry peers and simulation controls.
- Arduino handshake behavior.
- Live K-CAN TX enablement.

## 5. Required implementation changes

1. Rename `devices/steering-controller/` to
   `devices/servotronic-controller/` and update prose and internal symbols that
   unambiguously refer to the optional hardware. Application-facing “steering”
   names may remain where they describe the user feature rather than a device.
2. Extend `DeviceRole` with `SERVOTRONIC_CONTROLLER` and reduce
   `DeviceSource` to `PHYSICAL`, `EMULATED`, and `DISABLED`.
3. Add `DeviceLifecycleStatus` with the seven values fixed in the overview.
4. Add immutable catalogue and identity values. The default catalogue contains
   the two enabled roles, device ID 1, protocol version 1, and one permitted
   instance each.
5. Expand `CustomCanIds` and `protocol/custom.toml` with role-specific
   `hello`, `welcome_ack`, and `heartbeat` IDs.
6. Generalize `scripts/generate_custom_protocol.py` so the TOML definition,
   Python constants, Arduino header, and generated Markdown stay synchronized.
7. Add payload dataclasses and encode/decode functions for each registry frame.
8. Validate DLC, integer ranges, reserved bytes, response nibbles, and standard
   IDs at the codec boundary.
9. Document little-endian fields, response values, and the exact vectors from
   the overview.
10. Start removing `desired_led_colours`/`observed_led_colours` dependencies;
    do not introduce another public LED array in their place.

## 6. Public interfaces and types

The generated constants must include role-specific names equivalent to:

```text
CAN_ID_BUTTON_PAD_HELLO = 0x702
CAN_ID_BUTTON_PAD_WELCOME_ACK = 0x703
CAN_ID_BUTTON_PAD_HEARTBEAT = 0x704
CAN_ID_SERVOTRONIC_CONTROLLER_HELLO = 0x705
CAN_ID_SERVOTRONIC_CONTROLLER_WELCOME_ACK = 0x706
CAN_ID_SERVOTRONIC_CONTROLLER_HEARTBEAT = 0x707
CUSTOM_DEVICE_PROTOCOL_VERSION = 1
```

Domain types must represent:

```text
DeviceRole
DeviceSource
DeviceLifecycleStatus
DeviceIdentity(role, device_id)
DeviceCatalogueEntry(identity, enabled, supported_protocol_version)
```

Codec payloads must carry the fields and widths specified in the overview.
Do not expose raw byte offsets outside the protocol package and generated
firmware constants.

## 7. Expected files/modules affected

- `protocol/custom.toml`
- `protocol/custom_ids.md`
- `protocol/README.md`
- `scripts/generate_custom_protocol.py`
- `coordinator/src/e87canbus/protocol/generated.py`
- `coordinator/src/e87canbus/protocol/can.py`
- `coordinator/src/e87canbus/config.py`
- `coordinator/src/e87canbus/device.py` or a focused registry-domain module
- `devices/button-pad/include/can_ids.h`
- `devices/servotronic-controller/README.md`
- `devices/README.md`
- protocol, generator, configuration, and architecture tests
- repository documentation containing ambiguous device terminology

## 8. Detailed implementation sequence

1. Perform the terminology/directory rename and update imports/tests while
   preserving application-level steering names.
2. Model all eight project messages in `custom.toml`.
3. Refactor the generator around generic message definitions plus the special
   LED packing metadata.
4. Regenerate Python, Arduino, and Markdown outputs.
5. Add strict frame payload values and pure codecs.
6. Add catalogue/domain types and default configuration validation.
7. Add the fixed protocol vectors and negative vectors.
8. Run generated-artifact, protocol, config, and architecture checks.
9. Update documentation links and terminology.

## 9. Edge cases and failure behavior

- Reject any generated ID outside the standard 11-bit range.
- Reject duplicate arbitration IDs in configuration/generation.
- Reject invalid DLC and reserved bytes without partially decoding a payload.
- Keep status codes opaque except for zero/nonzero health semantics.
- Do not add capability bits or identity provisioning commands.
- Preserve `0x700` button and `0x701` LED payload compatibility.
- Do not treat a recognized arbitration ID on PT-CAN or F-CAN as registry
  traffic; network scoping remains part of routing.

## 10. Required tests and verification commands

Add tests for:

- all generated constants and stale-artifact detection;
- the three exact overview vectors on both role ID families;
- little-endian round trips;
- unsupported response code/version handling;
- wrong DLC, nonzero reserved bytes, field overflow, and wrong arbitration ID;
- default catalogue identities, source modes, and duplicate validation;
- absence of ambiguous hardware terminology in active runtime/contracts.

Run at minimum:

```text
uv run python scripts/generate_custom_protocol.py --check
uv run pytest coordinator/tests/test_generated_protocol.py coordinator/tests/test_can_protocol.py coordinator/tests/test_config.py coordinator/tests/test_architecture.py
```

Also run the repository's configured Python lint/type checks if protocol or
domain signatures require broader changes.

## 11. Exit criteria

- `custom.toml` is the single source for all eight project messages.
- Generated Python, Arduino, and Markdown artifacts are current.
- Exact positive and malformed vectors pass.
- Catalogue/domain vocabulary is complete and immutable.
- The optional hardware is consistently named Servotronic.
- No runtime registry behavior has been prematurely simulated or special-cased.

## 12. Required implementation-log update

After implementation, update the phase 1 row and append a phase 1 entry to
[the implementation log](implementation-log.md). Record generator design
changes, renamed paths, verification commands/results, and any compatibility
work deferred to phase 2. Do not mark the phase complete while required tests
fail.

## 13. Handoff notes for phase 2

Phase 2 must consume the generated codecs and catalogue directly. It must not
redeclare CAN constants, reinterpret byte layouts, or add a simulation-only
registration path.
