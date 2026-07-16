# Device registry and CAN handshake — proposed specification

**Status:** Proposed design for research and phased implementation.

## Purpose

Introduce a common registration and heartbeat protocol for the controller's
intelligent custom devices. The controller must know which supported devices
are presently compatible and communicating, without assuming every optional
device is installed.

The initial participants are:

- `button_pad` — the NeoTrellis CAN button pad.
- `servotronic_controller` — the optional controller for additional
  Servotronic assistance. It is not the steering rack and it is not required
  for normal hydraulic power-assisted steering (PAS).

The controller remains useful when either device is absent. Missing optional
hardware disables only the features that depend on it.

## Decisions already made

### Naming

Replace the ambiguous `steering_controller` name with
`servotronic_controller` (or the consistently chosen equivalent) in runtime
models, Socket.IO contracts, frontend labels, tests, documentation, and
firmware-facing protocol names.

The name must make clear that this is optional additional assistance layered
on normal hydraulic PAS. It must not imply software control of the steering
rack or a software-provided steering safety fallback.

### Source of truth for LED state

`buttons.led_colours` remains the one canonical controller-requested LED
state. It is the state displayed by normal UI, sent in LED command frames, and
used by both live and simulated operation.

Remove the current normal-UI use of the second 16-colour
`observed_led_colours` state. The existing virtual decoder remains useful as a
protocol implementation/test participant, but it does not need to mirror all
LED colours into application state.

The device registry heartbeat establishes that a device is alive, compatible,
and communicating. It does not prove that every individual LED command was
applied. No per-command acknowledgement is planned initially.

### Optional-device policy

`button_pad` and `servotronic_controller` are optional. Their absence,
staleness, incompatibility, or device-local fault must not make the controller
process globally unready by itself.

Feature availability is precise and is enforced both in the UI and on the
server command path:

- Button-pad controls require an active compatible `button_pad`.
- Additional Servotronic-assistance controls require an active compatible
  `servotronic_controller` and any other relevant inputs (for example, fresh
  vehicle speed).
- Vehicle telemetry and ordinary `/car` operation do not require either
  custom device.

When the Servotronic device is absent or stale, the controller sends no
additional-assistance command. The car continues with its ordinary hydraulic
PAS. The physical device's own firmware/hardware behaviour remains responsible
for whatever it does when controller traffic disappears.

### Passive vehicle telemetry is separate

Vehicle ECUs are not registry participants. The controller passively listens
for configured CAN signals and retains the latest valid sample plus freshness
state (`valid`, `stale`, or `never_observed`). It must not probe or scan
arbitrary vehicle CAN IDs by default.

Features gate on the exact inputs they need, rather than on a global
"car connected" flag.

## Current baseline

Today, simulated mode creates an in-memory topology, a virtual vehicle, a
virtual NeoTrellis node, and an in-process assistance actuator immediately at
startup. The virtual NeoTrellis can encode button input frames and decode LED
snapshot frames, but it has no boot/discovery/heartbeat lifecycle. The virtual
assistance actuator is an in-process model rather than a CAN-registering peer.

Live mode opens local SocketCAN interfaces and can observe button input frames,
but cannot prove that a physical button pad is powered, compatible, or has
applied an LED command. Existing process health verifies the controller,
storage, CAN readers, and local send failures; it is not a remote-device
presence check.

## Architecture

### 1. Static capability catalogue

Controller/device code and configuration define which roles are supported and
enabled. This is not dynamic discovery:

```text
Supported roles
  button_pad
  servotronic_controller
```

For each role, the catalogue defines supported protocol versions, permitted
capabilities, permitted instance count, heartbeat policy, command codec, and
feature dependencies.

### 2. Runtime device registry

The controller owner thread owns an in-memory registry. It is the canonical
answer to "which supported devices have recently registered and are usable?"
It is not persisted across controller restarts.

A registry entry contains at least:

```text
role
stable device ID
device boot/session ID
protocol version
advertised capability bits
status
last valid heartbeat time
last device-reported fault/status code, if any
```

The registry updates internal last-seen time for each valid heartbeat, but
publishes live state only when externally meaningful state changes. Heartbeats
must not create an unbounded browser update stream.

### 3. Stable identity

Use a provisioned 16-bit numeric device ID for the first protocol version.
The identity is:

```text
(role, device ID, current device boot/session ID)
```

- `role` distinguishes device type.
- `device ID` is a stable firmware-configured identity, initially normally
  `1` for the installed instance of each role.
- `boot/session ID` is regenerated on each device boot and distinguishes a
  reboot from stale traffic.

The controller configuration allow-lists expected role/ID pairs. Unknown or
duplicate identities are ignored or explicitly reported according to a
per-role duplicate policy; they never silently grant a feature capability.

A microcontroller hardware UID is not required for v1.

## Device lifecycle

### Controller registry lifecycle

```text
no valid registration
  → not_found

valid HELLO accepted
  → pending

valid acknowledgement/heartbeat for current session
  → active

heartbeat timeout
  → stale / unavailable

unsupported version or capabilities
  → incompatible

reported or detected device fault
  → fault
```

The exact public vocabulary should be finalised once and shared by backend,
frontend, schema, firmware documentation, and simulator tests.

### Device-local lifecycle

```text
booting → discovering → operational
                 ↘ incompatible / local fault

operational → controller_lost → discovering
```

The button pad owns its local visual behaviour. The intended first UX is:

- discovering: breathing pattern;
- operational: normal controller-requested LED display;
- controller unavailable or local fault after the bounded timeout: red error
  pattern.

This is a local firmware indication, not a claim that the controller can
observe physical LEDs without a status protocol.

## Protocol behaviour

The protocol is device-initiated:

```text
Device broadcasts HELLO repeatedly while discovering
  → Controller validates role, ID, version, and capabilities
  → Controller replies WELCOME / heartbeat acknowledgement
  → Device enters operational state and sends periodic heartbeat/status
  → Controller maintains an active registry lease while heartbeats are fresh
```

The controller does not scan arbitrary CAN traffic for devices. It listens for
the explicit custom-device protocol and acknowledges valid known devices. A
controller acknowledgement or beacon is required so that a device can know a
controller is presently listening.

Every message family must carry enough version, identity, session, and
sequence information to reject stale messages after either side restarts.
CAN bus CRC protects frame transport integrity; the protocol still needs its
own semantic validation. This design is not an authentication/security scheme;
the CAN bus trust model is a separate security decision.

### Initial message content

Final arbitration IDs and byte-level layouts are implementation work, but the
following semantic fields are required:

| Message | Required fields |
| --- | --- |
| `HELLO` | protocol version, role, stable device ID, device boot/session ID, capability bits, sequence |
| `WELCOME` / acknowledgement | protocol version, role, device ID, device boot/session ID, controller boot/session ID, sequence/echo |
| `HEARTBEAT` / status | identity/session fields, sequence, optional compact device-local fault/status code |

The v1 frame design must fit standard 8-byte CAN payloads and use IDs reserved
for this custom protocol. It must document byte order, field widths, malformed
frame handling, and compatibility rules.

### Timing defaults for research

Use these as starting points, not final physical guarantees:

- device discovery/heartbeat cadence: approximately 1 Hz with jitter;
- controller/device stale timeout: approximately three missed intervals;
- bounded retry/backoff after a fault or incompatible response;
- state publications only on lifecycle transitions, not every heartbeat.

The final values must be validated against bus load, startup UX, firmware
timers, and the required responsiveness of the optional feature.

## State, API, and UI projection

Replace the current broad device projection with a registry-oriented read-only
live projection. It should expose enough information for diagnostics and
feature availability without leaking mutable registry internals:

```text
devices:
  button_pad:
    configured identity
    source mode (physical/emulated/observer/disabled)
    lifecycle status
    protocol/capability summary
    last transition/fault summary
  servotronic_controller:
    same lifecycle information
```

The exact shape may remain a keyed device collection for future multiple
instances, but selectors must be narrow and preserve references for unchanged
entries. Replacing a parsed `devices.state` object must not re-render a button
pad solely because an unrelated Servotronic observation changed.

UI requirements:

- `/car`: show capability-specific "not found", "unavailable", or
  "incompatible" state where relevant; do not treat optional absence as a
  global failure.
- `/dev`: show registry status and, in simulation only, provide controlled
  fault/connection scenarios.
- Normal LED rendering always uses `buttons.led_colours`; it must not silently
  switch between requested and simulator-observed LED arrays.

## Simulation requirements

Virtual devices must implement the same protocol and state machines as their
physical counterparts. The controller must consume only protocol frames and
registry transitions, not a simulation-only success path.

The simulator needs deterministic controls (development UI and/or tests) for:

- device absent/no HELLO;
- delayed boot/discovery;
- successful registration;
- incompatible version/capabilities;
- heartbeat loss after registration;
- device reboot with a new boot/session ID;
- compact device fault status;
- malformed registration/status frame.

Use an injectable/fake clock in tests. Do not use wall-clock sleeps to test
timeouts. The current virtual vehicle remains a passive telemetry producer,
not a registry participant.

## Command and safety boundaries

Feature gating is not only frontend presentation. Backend command handling
must reject a feature command when its required active compatible device or
fresh input is absent.

The controller must not infer a physical safe state from a heartbeat timeout,
a local `send()` success, or the absence of an error. It may record only the
facts it observed: registry status, local CAN send outcome, and any explicit
device status frame.

For Servotronic enhancement, absence/unavailability means no additional
assistance capability is offered. It does not describe, prove, or control the
underlying hydraulic PAS behaviour.

## Compatibility and migration

No existing physical firmware must be supported. Make registration mandatory
for the first built physical-device firmware. A future passive/legacy observer
mode, if needed, must be explicit and must never be represented as a registered
compatible device.

## Verification expectations

The implementation plan should include protocol vectors and tests for:

- valid registration, re-registration, reboot, and timeout;
- malformed/incompatible/unknown/duplicate identity rejection;
- optional-device feature gating in both backend and UI;
- simulation and live-contract projection behaviour;
- no lifecycle update/render storm under heartbeat traffic;
- LED state remains controller-canonical;
- controller health/readiness stays separate from optional device availability.

## Handoff questions for planning

The planning phase should settle:

1. Final public status names and registry live-event schema.
2. Exact CAN arbitration IDs and 8-byte layouts for each v1 message.
3. Firmware provisioning workflow for role/device ID.
4. Final heartbeat, timeout, and retry values based on bus and UX constraints.
5. Per-role duplicate-instance and device-fault policies.
6. Exact `/car` status placement and `/dev` simulation/fault controls.
7. A safe migration sequence for renaming `steering_controller` to
   `servotronic_controller` across all contracts and implementation layers.
