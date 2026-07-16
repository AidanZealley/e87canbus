# Phase 5 — Button-pad firmware

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Agent prompt](phase-agent-prompt.md) ·
[Previous phase](phase-4-simulation-and-dev-ui.md) · Next: none

## 1. Objective

Implement the device side of the version 1 handshake in the existing Arduino
button-pad project, compile it against generated constants, and complete the
repository's software-only acceptance checks without claiming physical
NeoTrellis or in-car readiness.

## 2. Dependencies and starting state

- Phases 1–4 must be completed in the implementation log.
- Generated firmware constants and conformance vectors are authoritative.
- The current Arduino Micro project uses MCP2515 K-CAN at 100 kbit/s, decodes
  LED snapshots into memory, and contains fake periodic button traffic.
- Physical NeoTrellis topology/mapping remains unverified.

## 3. In scope

- Build-time stable device identity.
- EEPROM-backed boot/session counter.
- Nonblocking discovery, operational heartbeat, incompatibility, controller
  loss, and local-fault states.
- Strict acknowledgement validation.
- Operational gating for LED handling and future button-event calls.
- Logical display modes for later physical rendering.
- Removal of fake automatic input.
- PlatformIO and repository software verification.

## 4. Explicitly out of scope

- Physical NeoTrellis scanning or rendering.
- Selecting libraries, topology, brightness, current limits, or animations.
- Servotronic firmware.
- Bench test execution.
- Collision capture or in-car TX authorization.
- EEPROM stable-ID provisioning commands.

## 5. Required implementation changes

1. Fix the role to button pad and provide checked-in build configuration for
   `DEVICE_ID=1`, allowing an explicit build-time override.
2. Add the Arduino EEPROM dependency and store a 16-bit boot counter. Increment
   it once during startup and use the resulting value as the device session.
3. Keep all timing as unsigned wrap-safe `millis()` deltas; add no blocking
   handshake delays.
4. Send an immediate `HELLO`, then retry every one second with the defined
   jitter while discovering/controller-lost.
5. Validate `WELCOME_ACK` DLC, role-specific ID, protocol/response nibble,
   stable ID, device session, and echoed latest sequence.
6. On accepted welcome, store the controller session, enter operational, and
   send the first heartbeat without waiting a full interval.
7. Send heartbeats every one second with the current opaque status code and
   require matching acknowledgements.
8. Enter `controller_lost` after three seconds without a valid acknowledgement,
   select logical red error display, and resume HELLO.
9. On unsupported response, enter incompatible, select logical red error
   display, and retry HELLO every five seconds.
10. Represent local fault separately, continue heartbeat with nonzero status,
    and select logical red error display.
11. Accept `0x701` LED snapshots only in operational state with a fresh
    controller lease. Preserve validate-then-commit decoding.
12. Allow `sendButtonEvent` only in operational state. Leave the callable seam
    ready for future scanning but remove the periodic fake press/release loop.
13. Expose logical `discovering`, `normal`, and `error` display modes without
    claiming physical rendering.
14. Keep serial diagnostics bounded and useful for software/bench follow-up.

## 6. Public interfaces and types

Firmware compile-time interface:

```text
DEVICE_ID: unsigned 16-bit value, default 1
CUSTOM_DEVICE_PROTOCOL_VERSION: generated value 1
```

Internal state should use an explicit enum equivalent to:

```text
BOOTING
DISCOVERING
OPERATIONAL
CONTROLLER_LOST
INCOMPATIBLE
LOCAL_FAULT
```

Logical display mode is separate from contact state so later NeoTrellis code
can render breathing, normal requested LEDs, or red error without rewriting the
protocol state machine.

## 7. Expected files/modules affected

- `devices/button-pad/platformio.ini`
- `devices/button-pad/src/main.cpp`
- optional focused headers/source files under `devices/button-pad/include/` and
  `src/` if needed to keep protocol/state logic testable
- generated `devices/button-pad/include/can_ids.h` only through the generator
- `devices/button-pad/README.md` or `devices/README.md`
- firmware build/generator checks and any host-side vector tests
- root/simulation/protocol documentation if implementation details need
  clarification

## 8. Detailed implementation sequence

1. Add build-time identity configuration and validate its range at compile
   time where supported.
2. Implement EEPROM read/increment/write with a documented wrap rule.
3. Add payload builders/parsers using only generated offsets/constants.
4. Implement the nonblocking state machine and due-time helpers.
5. Route incoming ACK and LED frames through strict state-aware validation.
6. Gate button transmission and remove fake automatic traffic.
7. Add logical display-mode selection and serial transition diagnostics.
8. Compile with PlatformIO from a clean project build.
9. Run generators, coordinator, frontend, and architecture regression checks.
10. Update device documentation with the exact remaining physical gaps.

## 9. Edge cases and failure behavior

- EEPROM counter wrap is accepted; avoid treating zero as an invalid session
  unless the phase 1 shared contract explicitly reserves it.
- A failed EEPROM write/read must enter local fault rather than silently reuse
  an untrustworthy session.
- Ignore ACKs for old sequences or sessions without refreshing contact.
- Ignore LED frames while discovering, incompatible, controller-lost, or
  faulted unless future fault behavior explicitly permits normal display.
- CAN send failure is logged and retried only at the next bounded cadence; do
  not busy-loop.
- MCP2515 initialization failure remains a local fault and must not fall
  through into operational traffic.
- `millis()` rollover must not break cadence or timeout comparisons.
- The firmware remains bench-only despite compiling successfully.

## 10. Required tests and verification commands

Where practical, keep byte-layout behavior covered by the host-side generated
vector tests from phase 1. Add compile-time or extracted pure tests if firmware
logic is split into testable units.

Verify:

- generated header freshness;
- default and overridden device ID builds;
- EEPROM/session integration compiles;
- no fake periodic button event remains;
- all state transitions use nonblocking timing;
- ACK/LED validation matches the shared vectors;
- documentation retains bench/in-car warnings.

Run at minimum:

```text
uv run python scripts/generate_custom_protocol.py --check
pio run --project-dir devices/button-pad
uv run pytest coordinator/tests
cd frontend && pnpm test --run
cd frontend && pnpm build
```

If PlatformIO is unavailable, do not mark the phase complete. Record the
environment blocker and all other completed verification in the log.

## 11. Exit criteria

- The button-pad project compiles with the generated version 1 protocol.
- Boot/session identity changes across firmware boots through EEPROM.
- Symmetric contact loss and recovery behavior matches simulation.
- LED and future button behavior are operationally gated.
- Fake button traffic is removed.
- Full software verification passes.
- Documentation makes no physical-rendering, bench, collision, or in-car
  readiness claim.

## 12. Required implementation-log update

Update the phase 5 row and append a final phase entry listing firmware files,
identity/session behavior, build output, full regression results, deviations,
and every remaining physical evidence gate. Mark complete only if PlatformIO
and all required software checks pass.

## 13. Handoff notes for following work

Future work begins with isolated bench validation and verified NeoTrellis
hardware integration, followed by K-CAN collision capture. It must not infer
physical correctness from this software-only milestone.
