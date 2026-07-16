# Device registry and symmetric CAN handshake

**Status:** Approved implementation design.

This document supersedes the former root-level
`docs/device-registry-and-handshake.md` proposal and its rendered HTML copy. It
is the authoritative design for the first device-registry implementation. The
individual implementation phases are linked in [Implementation phases](#implementation-phases).

## Goals

The controller must know whether each supported custom device is present,
compatible, healthy, and communicating. It must do so without assuming that
optional hardware is installed and without treating passive vehicle ECUs as
registry participants.

The first participants are:

- `button_pad` — the NeoTrellis CAN button pad.
- `servotronic_controller` — an optional controller for additional Servotronic
  assistance. It is not the steering rack and is not required for ordinary
  hydraulic power-assisted steering.

The design provides:

- device-initiated registration;
- symmetric controller/device contact leases;
- explicit compatibility, staleness, and device-fault states;
- server-side feature gating;
- the same protocol in live, simulated, and firmware implementations;
- bounded state publication that does not emit on every heartbeat.

## Non-goals

Version 1 does not provide:

- dynamic discovery of arbitrary roles or CAN IDs;
- multiple instances of one role;
- capability negotiation;
- authentication, authorization, or protection against a malicious CAN peer;
- persisted registry state;
- per-command or physical-output acknowledgements;
- a physical Servotronic command/profile protocol;
- Servotronic firmware;
- physical NeoTrellis scanning, mapping, brightness, or pattern rendering;
- collision proof for the provisional CAN IDs;
- bench or in-car acceptance.

## Decisions and terminology

Use `servotronic_controller` consistently in runtime models, contracts,
configuration, UI labels, tests, documentation, protocol names, and device
directories. Do not use the ambiguous `steering_controller` name for the
optional hardware.

`buttons.led_colours` is the only public controller-requested LED state. Remove
normal application and UI use of `desired_led_colours` and
`observed_led_colours`. A virtual button-pad decoder may retain private decoded
state for protocol tests, but that state is not a second application truth.

Both custom roles are optional. Their absence, staleness, incompatibility, or
device-local fault is nonfatal and does not by itself make the controller
unready. Vehicle telemetry remains passive and separate; features depend on
the exact fresh inputs they require rather than a global “car connected” flag.

## Static device catalogue

The compiled catalogue contains exactly one configured identity per role:

| Role | Stable device ID | Protocol version | Instance limit |
|---|---:|---:|---:|
| `button_pad` | 1 | 1 | 1 |
| `servotronic_controller` | 1 | 1 | 1 |

The role is implied by role-specific arbitration IDs. The 16-bit stable device
ID is provisioned at build time. No capability bitmap or negotiation is
included in version 1.

Device sources are `physical`, `emulated`, or `disabled`. Simulation defaults
both roles to `emulated`. Live mode configures both as `physical` when K-CAN is
enabled, but the default live composition has no K-CAN transmit grant. It may
therefore observe a `HELLO` and remain `pending`, but cannot activate a device
until acknowledgement transmission is explicitly authorized.

## Wire protocol

All registry traffic uses standard 11-bit CAN IDs on K-CAN. The allocation is
provisional and must not be enabled in-car before collision validation.

### Arbitration IDs

| ID | Direction | Message |
|---|---|---|
| `0x700` | Button pad → controller | Existing button event |
| `0x701` | Controller → button pad | Existing complete LED snapshot |
| `0x702` | Button pad → controller | `HELLO` |
| `0x703` | Controller → button pad | `WELCOME_ACK` |
| `0x704` | Button pad → controller | `HEARTBEAT` |
| `0x705` | Servotronic → controller | `HELLO` |
| `0x706` | Controller → Servotronic | `WELCOME_ACK` |
| `0x707` | Servotronic → controller | `HEARTBEAT` |

### Encoding rules

All handshake frames have DLC 8. Multi-byte integers are unsigned
little-endian values.

`HELLO`:

| Byte | Field |
|---:|---|
| 0 | Protocol version, initially `1` |
| 1–2 | Stable device ID |
| 3–4 | Device boot/session ID |
| 5 | Sequence |
| 6–7 | Reserved; must both be zero |

`WELCOME_ACK`:

| Byte | Field |
|---:|---|
| 0 | Controller protocol version in the high nibble; response code in the low nibble |
| 1–2 | Echoed device ID |
| 3–4 | Echoed device session ID |
| 5–6 | Controller session ID |
| 7 | Echoed device sequence |

Response code `0` means accepted and code `1` means unsupported protocol
version. All other response codes are reserved in version 1.

`HEARTBEAT`:

| Byte | Field |
|---:|---|
| 0–1 | Stable device ID |
| 2–3 | Device session ID |
| 4–5 | Controller session ID |
| 6 | Sequence |
| 7 | Device status code |

Status code `0` is healthy. Any nonzero status is an opaque, role-specific
fault code. Meanings can be documented later without changing the registry
frame.

Example vectors for device ID `1`, device session `0x1234`, controller session
`0xABCD`, and button-pad IDs are:

```text
HELLO seq 0x56
  ID 0x702  data 01 01 00 34 12 56 00 00

accepted WELCOME_ACK
  ID 0x703  data 10 01 00 34 12 CD AB 56

healthy HEARTBEAT seq 0x57
  ID 0x704  data 01 00 34 12 CD AB 57 00
```

The Servotronic vectors use the same payloads on IDs `0x705`–`0x707`.

### Validation and sequences

- Unknown device IDs are ignored and logged without a response.
- A recognized ID with the wrong DLC, nonzero reserved bytes, or invalid field
  encoding increments malformed-frame diagnostics without changing registry
  state.
- A structurally valid `HELLO` from the configured identity with an unsupported
  version changes the registry to `incompatible` and receives an unsupported
  response when TX is available.
- Sequences wrap modulo 256. A forward delta of 1–127 is newer, delta 0 is an
  exact duplicate, and delta 128–255 is older/out of order.
- An exact duplicate for the current sessions may be re-acknowledged without a
  public state change. Older/out-of-order frames are ignored.
- Session matching, not sequence alone, prevents a previous boot from renewing
  a current lease.
- The device accepts only acknowledgements matching its role-specific ID,
  stable ID, device session, latest sequence, and expected controller session.

The existing button-event and LED-snapshot payloads remain unchanged. Their
session binding is established by the active lease: the controller accepts
button events only from an active role, and the device accepts LED snapshots
only while operational with a fresh controller lease. Legacy firmware that
sends button events without registering is ignored.

## Symmetric handshake and timing

The device initiates the relationship:

```text
device HELLO
  → controller validates configured identity and version
  → controller WELCOME_ACK
  → device sends first HEARTBEAT
  → controller becomes active and acknowledges every heartbeat
```

The controller uses received heartbeats as its device-contact lease. The
device uses received acknowledgements as its controller-contact lease.

Timing constants are:

- `HELLO` cadence: 1 second with up to ±100 ms jitter;
- heartbeat cadence: 1 second with up to ±100 ms jitter;
- ordinary contact timeout: 3 seconds;
- incompatible retry: 5 seconds;
- incompatible observation timeout: 15 seconds.

Tests inject a fake monotonic clock and zero jitter. They must not use
wall-clock sleeps.

After a controller restart, its 16-bit session changes. A device still using
the previous session receives no valid acknowledgements, enters
`controller_lost` after three seconds, and resumes `HELLO`. No controller
beacon or special resynchronization frame is added in version 1.

## Lifecycle

### Controller registry states

The public vocabulary is fixed:

- `disabled`
- `not_found`
- `pending`
- `active`
- `stale`
- `incompatible`
- `fault`

```text
enabled startup ───────────────────────────────→ not_found
compatible HELLO ──────────────────────────────→ pending
pending + first healthy HEARTBEAT ─────────────→ active
pending + first nonzero HEARTBEAT ─────────────→ fault
active/fault + ordinary timeout ───────────────→ stale
unsupported HELLO ─────────────────────────────→ incompatible
incompatible + 15 s without another HELLO ─────→ stale
fault + healthy HEARTBEAT ─────────────────────→ active
any observed state + new compatible session ───→ pending
```

A new compatible `HELLO` for the configured role/device ID replaces the prior
session as a reboot. Version 1 deliberately defers duplicate quarantine. The
latest valid `HELLO` wins, frames for the displaced session are rejected, and
two devices misprovisioned with the same identity may cause visible flapping.

### Device-local states

```text
booting → discovering → operational
                    ↘ incompatible
operational → controller_lost → discovering
operational ↔ local_fault
```

Initial discovery selects a logical breathing display. Controller loss or a
local fault selects a logical red error display. A faulted device continues to
heartbeat with its nonzero status so contact and health remain distinct.
Physical rendering of those logical modes is deferred.

## Registry ownership and publication

`CoordinatorKernel` owns the immutable in-memory registry and is the only
state-changing owner. The protocol router decodes registry messages into typed
kernel inputs. Registry responses are typed controller effects executed
through the same `SafeCanTransmitter` and K-CAN rate policy as other writes.

Every valid heartbeat refreshes internal lease time. A heartbeat that changes
neither lifecycle nor public diagnostics does not change the `devices` topic,
produce a Socket.IO event, or replace frontend registry-entry references.

Registry state is discarded on controller restart. It is evidence of recent
compatible communication, not proof that a command or physical output was
applied.

## Feature gating

### Button pad

- Accept button frames only while `button_pad` is `active`.
- Send LED snapshots only while `button_pad` is `active`.
- Send the complete current canonical LED snapshot when the pad becomes
  active.

### Servotronic

A steering operation is available only when:

1. `servotronic_controller` is `active`;
2. a healthy Servotronic output adapter exists in the selected composition;
3. inputs required by that operation, such as fresh speed for Auto output, are
   valid.

Reject these HTTP operations with status `409` and error code
`feature_unavailable` while the feature is unavailable:

- steering mode/manual-level changes;
- maximum-assistance changes;
- active curve or saved-profile activation.

Saved-profile list/create/edit/delete remains available because it is durable
configuration storage, not a live-device operation. The `/car/steering` screen
is nevertheless unavailable until its live feature dependencies are met.

When Servotronic leaves `active`, emit no further assistance effects and clear
temporary maximum assistance. Retain the previously established normal mode,
manual level, and active curve, but reject changes until the device becomes
available again. Synchronize that retained normal state after reactivation.

## Canonical LEDs and failed-button feedback

`buttons.led_colours` includes both the normal requested display and temporary
controller-requested feedback. It never silently switches to simulator
observation.

When a mapped button action is unavailable, rejected by validation, or has an
immediately observable local execution failure:

- overlay red on the originating button for 500 ms;
- maintain an independent deadline for each button;
- restart only that button's deadline on a repeated failure;
- allow several buttons to be red concurrently;
- restore the normal canonical colour when each deadline expires;
- leave unassigned buttons and ordinary idempotent no-ops unchanged;
- do not recursively request feedback if the red LED send itself fails.

Effects carry an optional originating button index so a synchronous failure
can be correlated. Without a remote command acknowledgement, this feedback
cannot claim that physical target hardware applied a command.

## Live contract

The unreleased Socket.IO version 1 contract is updated in place. Backend and
frontend changes must land together, and the generated
`protocol/live-events-v1.schema.json` remains authoritative.

```text
devices:
  registry:
    button_pad: DeviceRegistryEntry
    servotronic_controller: DeviceRegistryEntry
  networks: [...]
```

Each entry exposes:

```text
role
label
device_id
source_mode
status
protocol_version | null
device_session_id | null
last_status_code | null
last_transition_monotonic_s | null
```

Do not expose controller sessions, heartbeat sequences, retry counters, or
last-heartbeat timestamps. Move existing effective-assistance and watchdog
observations from `devices.steering_controller` to nullable
`steering.servotronic`. Optional device and adapter faults remain nonfatal.

Frontend store application merges entries by role and preserves an unchanged
entry's object reference. A Servotronic transition must not re-render a
component selecting only the button-pad entry.

## User interfaces

### `/car`

- Show only devices observed during the current controller boot in the
  overview footer.
- Hide `disabled` and `not_found`.
- Retain `pending`, `active`, `stale`, `incompatible`, and `fault` entries until
  recovery or controller restart.
- Show the exact unavailability reason inside dependent screens.
- Make the steering screen and overview assistance output unavailable when
  Servotronic registration or its output adapter is unavailable.
- Do not turn optional-device absence into a global failure banner.

### `/dev`

Use a reusable `SimulatedDeviceCard` for both virtual devices. It owns the
registry badge and lifecycle actions and renders device-specific controls as
children.

Controls manipulate the virtual peer rather than setting registry state:

- connect starts a new session and sends `HELLO`;
- disconnect stops all frames and naturally becomes stale;
- reboot changes session and re-handshakes;
- incompatible firmware sends a bad-version `HELLO`;
- fault sends a nonzero heartbeat status;
- reset restores both peers as present, compatible, and healthy.

Malformed frames and duplicate identities remain test-only cases.

## Firmware identity and sessions

The button-pad firmware project fixes its role and accepts `DEVICE_ID` as a
build-time setting with checked-in default `1`. No runtime identity
provisioning tool is added.

The Arduino increments a 16-bit EEPROM boot counter once per boot and uses it
as the device session. Counter wrap is accepted; 65,536 device reboots within
one controller session are outside the operating assumption. Firmware timers
use wrap-safe `millis()` arithmetic and no blocking delays.

This phase removes periodic fake button events. It implements registration,
heartbeat/acknowledgement loss, logical display modes, and operational gating,
but defers physical NeoTrellis scanning and rendering.

## Health and safety boundaries

- Registry absence, staleness, incompatibility, device fault, and optional
  adapter failure do not by themselves make controller readiness false.
- Existing controller-owned faults such as fatal reader, inbox, or local CAN
  execution failures retain their documented health behavior.
- A successful local `send()` proves only local submission.
- A heartbeat proves recent compatible communication, not command application.
- Servotronic absence means no additional-assistance capability is offered. It
  makes no claim about underlying hydraulic PAS.
- Live K-CAN acknowledgement TX remains disabled until explicit grant and
  physical evidence requirements are satisfied.

Relevant architectural decisions are [ADR 0004: generated custom protocol](../decisions/0004-generated-custom-protocol.md),
[ADR 0005: atomic button LED snapshots](../decisions/0005-atomic-button-led-snapshots.md),
[ADR 0006: evidence-gated hardware behavior](../decisions/0006-evidence-gated-hardware-behavior.md),
and [ADR 0008: unified controller architecture](../decisions/0008-unified-controller-architecture.md).

## Deferred evidence gates

Before any in-car handshake transmission:

1. Capture the real K-CAN traffic on this vehicle.
2. Demonstrate that `0x700`–`0x707` do not collide.
3. Verify transceiver voltage compatibility, bitrate, termination, isolation,
   loading, and grounding.
4. Perform isolated 100 kbit/s bench registration, loss, recovery, LED-gating,
   and button-gating tests.
5. Enable K-CAN TX only through the existing explicit configuration and grant
   boundaries.

Physical Servotronic output behavior additionally remains subject to its own
hardware and evidence decisions.

## Implementation phases

1. [Phase 1 — Specification and protocol](phase-1-specification-and-protocol.md)
2. [Phase 2 — Kernel registry and gating](phase-2-kernel-registry-and-gating.md)
3. [Phase 3 — Live contract and `/car` UI](phase-3-live-contract-and-car-ui.md)
4. [Phase 4 — Simulation and `/dev` UI](phase-4-simulation-and-dev-ui.md)
5. [Phase 5 — Button-pad firmware](phase-5-button-pad-firmware.md)

Agents must read the [implementation log](implementation-log.md) before
starting and update it after completing or blocking a phase. Use the reusable
[phase agent prompt](phase-agent-prompt.md) for each handoff.
