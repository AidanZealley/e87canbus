# Phase 2: physical coordinator panel and Pi integration

Status: host software, firmware, and repeatable Pi provisioning implemented; physical bench
acceptance remains pending. [Phase 1](phase-1-simulator.md) is complete.

## Outcome

Implement the approved Phase 1 behavior on the Raspberry Pi 4, QT Py RP2040, NeoPixel Driver BFF,
five-pixel strip, and momentary hotspot button. Provisioning and runbooks must make a fresh Pi
installation repeatable, and bench evidence must cover startup, normal operation, failures,
recovery, and shutdown before the enclosure geometry is finalized.

Physical work must reuse the independent `LocalControlsService`, its shared state derivation, and
its ports from Phase 1. The UART and NetworkManager implementations plug into that sibling service;
they must not move it into `ControllerLoop` or the kernel. Firmware owns rendering and link-loss
behavior only; it must not acquire hotspot policy, CAN interpretation, or vehicle application
state.

## Scope

- Add a PlatformIO firmware project at `devices/coordinator-panel/`.
- Define and implement the version 1 UART protocol.
- Add the `/dev/serial0` panel adapter.
- Add narrowly scoped NetworkManager hotspot control and client observation.
- Select physical adapters for the `car` and `bench` compositions.
- Extend Pi provisioning and deployment documentation.
- Validate the assembled electronics and approved behavior on the bench.

## UART protocol

Use bounded newline-delimited ASCII messages over 3.3 V UART. Version 1 requires only complete,
idempotent state refreshes and debounced button presses:

```text
RP2040 -> Pi
PANEL 1 HELLO
PANEL 1 BUTTON <sequence>

Pi -> RP2040
PANEL 1 STATE <starting|ready|hotspot_waiting|hotspot_connected|fault|off>
```

Protocol requirements:

- The Pi sends the complete current `STATE` at connection and every 500 ms thereafter. The refresh
  is also the heartbeat; there is no separate ping or state-delta protocol.
- The RP2040 sends `HELLO` periodically until it receives a valid state.
- `BUTTON` reports only the debounced press edge. Its wrapping sequence number lets the Pi discard
  a duplicate without acknowledging or replaying it.
- Both sides use fixed receive buffers, reject oversized lines, ignore malformed messages, and
  reject unsupported versions.
- A reconnect applies the latest state. Neither side queues missed states or button presses.
- Diagnostics may count invalid input, but arbitrary received text must never be logged without a
  length bound.

Checksums, acknowledgements, commands for individual pixels, configuration negotiation, and remote
firmware updates are out of scope unless bench evidence shows the direct UART link needs them.

## Firmware behavior

The firmware should be a small compiled C++ PlatformIO application and own:

- Immediate white travelling startup animation before Linux is available.
- Rendering all six approved semantic states across five pixels.
- A conservative compile-time brightness ceiling.
- Approximately 30 ms button debounce using the internal pull-up.
- UART parsing and button sequence generation.
- Initial communication grace and established-link heartbeat timeout.

Initial timing targets are a 60-second grace for the first valid Pi state and a two-second timeout
after communication has been established. A missed established heartbeat selects solid red locally.
Receiving a later valid state recovers immediately. After receiving `off`, the pixels remain off
until a new valid state arrives or the panel reboots, so a graceful Pi shutdown does not turn red
merely because heartbeats stop.

The accepted Phase 1 animation timings are requirements for the firmware: the white startup travel
uses a 1.4-second cycle with a 140-millisecond stagger between adjacent pixels, and the cyan
hotspot-waiting pulse uses a 1.8-second cycle. Both should have the simulator's smooth ease-in-out
character within the limits of the discrete firmware animation loop; frame-exact browser matching
is not required.

The RP2040 must not enable the hotspot itself or retain a button press for later delivery. A press
before a usable Pi connection may be ignored locally.

Host-side tests should exercise the parser, debounce state machine, animation selection, timeouts,
sequence wrapping, and bounded handling of malformed input without requiring the board. Physical
tests remain necessary for actual NeoPixel rendering and UART behavior.

## Pi panel adapter

The adapter owns `/dev/serial0`, bounded reading and writing, reconnect behavior, and link
diagnostics. It translates UART lines into the Phase 1 panel protocol without interpreting hotspot
or controller policy.

The local-controls service should begin driving `starting` before persistence and controller
initialization where the application lifecycle permits. It sends `ready` only after the existing
controller readiness requirements have been met. Graceful application shutdown sends `off` before
closing UART.

Failure to open or maintain the panel link is published as local-controls health. It does not mutate
vehicle application state or manufacture a CAN/kernel fault. During an actual outage the firmware,
not an unreachable Pi command, owns the red display.

Serial reads, writes, reconnects, and timeouts are owned outside the controller inbox. They must not
block CAN processing, alter controller readiness, or increment controller revisions.

## NetworkManager adapter

The adapter may operate only one predefined, root-created hotspot connection. It must support:

- Inspecting disabled, activating, active, deactivating, and failed state.
- Activating the named connection.
- Deactivating the named connection.
- Reporting whether at least one client is present on the hotspot interface.
- Forcing the managed hotspot off at coordinator startup and attempting to turn it off during
  graceful shutdown.

The connection must use `autoconnect=no`. SSID, password, interface, fixed address, and connection
identity belong to Pi provisioning rather than application-editable settings.

The service continues running while NetworkManager transitions and ignores additional button
presses until the observed state is stable. Command failure selects the shared hotspot fault and
panel fault state; it must not leave optimistic `active` state behind.

Initial client detection may treat any valid neighbour on the hotspot interface and subnet as a
connected laptop. The implementation and accepted neighbour states must be validated on the target
Pi. MAC-specific identity is deferred until multiple clients create a real ambiguity.

The `e87canbus` account remains unprivileged. Provisioning must use the narrowest NetworkManager
connection ownership or policy supported and demonstrate that the account can activate and
deactivate the managed hotspot without gaining permission to edit it or manage unrelated
connections. The controller service must not run as root.

The implemented boundary is a root-owned argument-validating helper exposed through one sudoers
entry. It accepts only inspect, activate, and deactivate command shapes for the fixed UUID and
interface. NetworkManager `connection.permissions` was unsuitable because it requires an active
login session; a general Polkit network-control grant would be wider than the helper.

## Pi provisioning

Extend `scripts/setup_pi.sh` and the fresh-Pi runbook to cover:

- Enabling the primary UART.
- Removing the Linux serial console from the UART.
- Preserving the deliberately selected Bluetooth behavior on the Pi 4.
- Granting the service account access to `/dev/serial0`.
- Installing required serial and NetworkManager dependencies.
- Creating or reconciling the non-autoconnecting hotspot connection without printing its password.
- Installing the narrow service-account permission mechanism.
- Verifying the resolved UART device and hotspot connection after reboot.
- Flashing the QT Py and recording the firmware version under test.

Provisioning must be idempotent and must not alter unrelated NetworkManager connections. Secrets
must not be committed to the repository or exposed in command output.

## Wiring and electrical constraints

Use the wiring recorded in [the context document](context.md): Pi 5 V, ground, BCM14/TXD and
BCM15/RXD to the QT Py power and crossed UART pins; BFF NeoPixel data on A3; button from a confirmed
free input such as A0 to ground.

Before making the loom:

- Confirm actual QT Py and BFF pin labels and connector orientation.
- Confirm the button pin does not conflict with the assembled BFF.
- Confirm UART voltage levels and common ground.
- Resolve the competing-supply/back-power behavior before connecting QT Py USB-C while the Pi
  harness is attached.
- Keep the LED run short and enforce the firmware brightness ceiling.

Bulk capacitance or additional data protection should be added only if measured startup glitches,
flicker, or supply behavior justify a deliberate board-mounted revision.

## Bench validation

Use the checkable [bench evidence record](bench-validation.md). Phase 2 must remain incomplete until
that record contains observations from the assembled Pi, panel, strip, button, and laptop.

Record evidence for:

- RP2040 power-up long before Linux and within the initial grace period.
- Linux boot exceeding the grace period, followed by recovery when communication starts.
- Coordinator startup, readiness, restart, fatal failure, and graceful shutdown.
- Hotspot enable, client arrival, client departure, disable, and NetworkManager failure.
- Presses before readiness and during hotspot transitions being discarded.
- UART disconnect, heartbeat timeout, reconnect, duplicate sequence, and malformed input.
- Missing CAN interface or reader failure producing the approved coordinator fault indication.
- NeoPixel colour, brightness, animation cadence, startup behavior, and light-pipe diffusion.
- Repeated power cycles without spurious hotspot activation or unexpected retained state.

Tests involving ignition-controlled power loss or SD-card hold-up are observations only unless a
separate power architecture has been designed. This phase does not claim graceful behavior after
uncontrolled removal of Pi power.

## Acceptance criteria

Phase 2 is complete when:

- Physical behavior matches every accepted Phase 1 state and transition.
- The simulator and physical compositions use the same state derivation and service owner.
- The physical adapters remain behind the Phase 1 ports and cannot block or fault the vehicle
  controller owner.
- The panel starts independently, detects loss of an established Pi link, and converges after
  reconnection.
- The hotspot is off after normal startup and graceful shutdown and cannot be toggled by an early or
  transitional press.
- The service account has only the demonstrated serial and managed-hotspot authority it requires.
- A fresh Pi can be provisioned and validated from the checked-in runbook without undocumented
  manual configuration.
- Bench evidence is sufficient to choose final LED spacing, light-pipe geometry, and brightness.

## Non-goals

- Making the panel a CAN node.
- Runtime-configurable LED programs or arbitrary colours.
- Root execution of the coordinator.
- General Wi-Fi administration from the application.
- MAC-specific client identity without demonstrated need.
- Remote RP2040 firmware updates.
- Ignition shutdown, battery protection, or a Pi hold-up power supply.
