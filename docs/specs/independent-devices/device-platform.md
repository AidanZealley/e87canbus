# Device platform

- **Status:** Proposed
- **Date:** 2026-09-16

## Goal

Define how a project device operates, stores its configuration and talks to the coordinator, so
every current and planned device follows one contract. A device must perform its primary function
from directly decoded vehicle data before it has ever reached the coordinator, and must keep
performing it if the coordinator is lost.

This follows [the live event transport](live-event-transport.md), which proves server-sent events
against the frontends first. It is the groundwork for
[device firmware provisioning](device-firmware-provisioning.md). Three of its decisions cross that
boundary and nothing else does: the flash partition layout, the contents of the identity partition,
and DHCP addressing.

## Scope

In scope: the transport rule, the configuration document and its store, device addressing, what
each device does when the coordinator is unreachable, flash layout, network membership, the
coordinator changes this requires, and the removal of the superseded CAN protocol.

Out of scope: firmware update over the network, flash encryption and secure boot, credential
rotation, cockpit board selection, and any device-to-device communication.

## Transport rule

> CAN is the car. Devices read vehicle data from it and actuate the car on it. Wi-Fi is the only
> channel between a device and the coordinator.

A device decodes the vehicle signals it needs from K-CAN itself. The coordinator does not republish
values already present on the bus. A device may transmit onto CAN to actuate the car, subject to
the existing collision, termination and grant validation.

Devices never communicate with each other, on any transport. This is not a CAN rule that Wi-Fi
happens to inherit. A device addresses the coordinator and nothing else, and has no awareness that
other project devices exist. Device-to-device communication is the only variant that would create a
second commanding authority, which is why ADR 0017 rejects it permanently rather than deferring it.

Everything between a device and the coordinator runs over mutually authenticated HTTPS on the
network defined by [the Wi-Fi device network](../wifi-device-network.md): one SSE stream at
`/api/devices/stream`, ordinary requests in the other direction.

## The coordinator sends state, not actions

The coordinator never tells a device to perform a momentary action. It publishes the device's
current desired state, and the device decides how to render or actuate it.

This removes the override channel that previously let the coordinator drive a button-pad LED effect
directly. Press feedback, connection indication and any other response to a device's own inputs are
firmware behaviour driven by the device's configuration. Nothing driver-visible waits on a
coordinator round trip, and no effect needs compositing against a base scene.

The disconnection case shows why this is a correctness fix rather than a simplification. Only the
pad can know the pad is disconnected, because any signal saying so would have to travel over the
link that is broken.

The rule that settles what each device resolves for itself:

> A device resolves locally exactly what it has local inputs for.

The button pad's only local input is its own buttons, so press feedback and connection state are
local and everything else arrives as a coordinator-resolved scene. The cockpit has live CAN data,
so it resolves displayed values locally and takes layout and limits from configuration. The
servotronic controller has CAN speed, so it resolves assistance locally from its stored curve.

## Configuration

The coordinator owns what configuration means. Transport, caching and provisioning never parse it.

There is one configuration document per device. It is an opaque byte payload in a versioned
envelope:

```json
{
  "schema_version": 1,
  "generation": 42,
  "payload_sha256": "<64 hex characters>",
  "payload": "<base64, at most 8192 decoded bytes>"
}
```

`schema_version` belongs to that device role's document type and is not a global version.
`generation` is monotonic per device and increments on any change.

The coordinator publishes the document as a `configuration` event on the device's stream, so a
change reaches the device as soon as it is made. There is no polling interval. A device that has
just connected receives the current document before anything else, and `Last-Event-ID` resume works
as described in the transport specification.

Three rules make opacity safe:

- A document replaces the entire configuration atomically. A partial or failed write is never
  applied. This carries ADR 0005's whole-scene semantics onto the new transport.
- A device that does not recognise `schema_version` keeps its last stored document and reports the
  mismatch in its status. It never merges, migrates or guesses.
- A device validates length and digest before committing, and rejects a payload over the 8 KiB
  bound without reading it.

Adding a device means adding a document type on the coordinator and a parser in that device's
firmware. It changes nothing in this specification, in the configuration store, or in `e87ctl`.

## Persistence

The device stores its configuration document and restores it at boot. Whatever was current at
power-off is what the device starts from.

There are no field-level exceptions and no expiry. Stored configuration may include values that
change how the car behaves, including an elevated steering assistance override that survives an
ignition cycle. What makes that acceptable is that one operator configures these values and the
devices displaying them restore their own state from the same power-off, so a restored override is
visible rather than surprising.

Two mechanisms were designed to prevent that and then removed, so neither is an oversight:

- A durable-versus-live split, where momentary values carried a lease and expired back to
  configuration-derived behaviour. It taxed every device with a second document type and expiry
  machinery to protect one field on one device.
- A requirement that vehicle-affecting stored state have an equally durable indication. It made the
  servotronic's behaviour depend on the button pad's configuration containing a particular button,
  which is the cross-device coupling this architecture exists to avoid, and it could only ever have
  been honoured by convention.

Do not reintroduce either without an argument that engages with those reasons.

Connection state is the only freshness signal a device has, and it drives what the device shows,
not what it does. A device that loses its stream keeps running on its stored configuration and
indicates the loss.

## Device addressing

The certificate SAN that `hosts/src/e87canbus/api/auth.py` already parses carries both facts the
coordinator needs:

```text
urn:e87canbus:device:v1:<installation>:<role>:<device-id>
```

The role selects the document type. The device ID selects which document. A device advertises
nothing; both values are authenticated rather than claimed.

Configuration is keyed by device ID from the start. With one device per role that is a dictionary
with one entry per role, and it costs nothing, but it means a role with several installed devices,
a sensor repeated in different positions, needs no change to the transport or the addressing.

A connecting device with no stored configuration receives its role's default document. With one
device per role that is always correct and no unconfigured state is ever visible. Assigning a
specific configuration to a specific device belongs in the console UI and is built when a role
first has more than one device, not before.

Reflashing a device generates a new device ID, so it returns as a device with no stored
configuration and receives the role default. That is rare and arguably correct.

Per-device configuration on the coordinator is application state of the same kind as the existing
steering profiles. It is not the device inventory ADR 0015 refuses, which is about `e87ctl` holding
a hidden database of device identity and secrets.

## Presence

Devices are HTTPS clients. The coordinator never initiates a connection to a device, broadcasts
anything, or discovers anything. An absent device costs nothing because there is no connection.

Presence is three separate things, two of which already exist:

- `DeviceRole` in `hosts/src/e87canbus/domain/devices/catalogue.py` is the vocabulary of roles the
  repository knows about. It is a compile-time constant.
- `DeviceSource`, already `physical`, `emulated` or `disabled` per composition, says which roles
  this installation has. This is what stops the console showing a permanently disconnected
  servotronic in a car without one.
- An open stream says whether a composed device is present right now. This is the only new piece
  and it replaces the CAN `HEARTBEAT` frame.

The coordinator holds at most one stream per device ID and lets a new connection supersede the old
one. A device whose TCP connection black-holes will reconnect while the coordinator still believes
the previous stream is alive, and without replacement those accumulate as writes into dead sockets.

Devices report status with `POST /api/devices/status` on change and on a heartbeat interval.

## Device contract

Every device, regardless of function:

1. Boots and runs its primary function from decoded CAN data and its stored configuration, without
   waiting for a network.
2. Applies a safe compiled-in default when it has no stored configuration, because provisioning
   installs none.
3. Joins the installation Wi-Fi network with provisioned credentials and authenticates with its
   provisioned client certificate.
4. Holds one SSE stream, applies configuration documents atomically, and reports status.
5. Renders immediate local feedback for its own inputs.
6. Fails closed on the network and open on its function. A device with missing or invalid identity
   never joins the network and still performs its primary function.

Device roles use hyphenated lowercase names in certificates, matching the SAN grammar already
enforced in `auth.py`: `button-pad`, `servotronic-controller`, `cockpit`. `DeviceRole` becomes the
single source of that vocabulary once its dependency on the generated protocol is removed.

## Operation without the coordinator

Each device states what it does when its stream is down. This is product behaviour and belongs in
each device's README alongside its wiring.

The existing AVR firmware does not implement any of this and is not ported. What follows is the
contract the replacement firmware is written against, in its own later specifications. The first
firmware built here is a link probe provisioned as `button-pad`, which only proves the network
path: it joins, authenticates, holds its stream and posts status, with no CAN, no configuration
parsing and no LED output.

**Servotronic controller.** Evaluates its stored assistance curve against speed decoded directly
from CAN. That is the complete Servotronic function, so operating without the coordinator is its
normal mode rather than a fallback. Profile selection and manual level arrive as configuration and
persist. This strengthens ADR 0007.

**Button pad.** Keeps lighting its stored scene and keeps rendering local press feedback and
connection state. Presses reach nobody while the stream is down, which is accepted. This is the one
interaction a coordinator outage genuinely costs.

**Cockpit.** Keeps drawing live values decoded from CAN using its stored layout and limits, and
distinguishes stored from coordinator-confirmed configuration in what it shows, as ADR 0012
specified.

High-beam actuation stays with the coordinator, which owns its own CAN transmitter, so no device is
in that path. If actuation ever moves onto a device, the deciding input and the actuation belong on
the same device so that no momentary action crosses the link.

## Flash layout

Devices are ESP32 parts with integrated TWAI. The partition table is part of the firmware artifact
and `e87ctl` writes to its offsets, so it is fixed before any board ships. Changing it afterwards
means physically erasing every device.

Four regions matter:

- the application, in two OTA slots with `otadata`;
- `nvs`, the firmware's own runtime state;
- `e87id`, the provisioned identity partition; and
- `e87cfg`, the configuration store.

`e87id` and `e87cfg` are separate NVS partitions rather than namespaces in one, so provisioning can
replace identity without destroying stored configuration and reflashing firmware destroys neither.
NVS provides atomic commit and wear levelling, so the store does not hand-roll slot flipping: a
document commits payload, generation and digest together or not at all.

Reserving two OTA slots is deliberate machinery for work that is out of scope. Network firmware
update is not in this milestone and may never be built. But these boards end up behind a dash, the
alternative to reserving the space now is physically pulling and erasing every device later, and
the space costs nothing while unused. The first firmware runs from the first slot and never writes
the second.

## Network membership and identity

Devices obtain an address by DHCP from the coordinator's existing `dnsmasq` pool. Static assignment
would require `e87ctl` to track which device holds which address, and ADR 0015 refuses to keep that
inventory. Identity comes from the certificate SAN, so the source address carries no authority. The
pool widens to cover devices; the console keeps its static `10.42.0.2`.

Nothing on the network enforces the rule that devices never address each other. Two clients of the
same access point can reach each other through it, and the existing disabled IP forwarding does not
change that. Access-point client isolation was considered and rejected: every device on this network
runs firmware from this repository, a compromised device already holds a valid certificate for the
coordinator's API, and the second-authority problem the rule exists to prevent comes from someone
deliberately building a device-to-device path rather than from one being reachable. It is a design
rule, kept by writing it down. Revisit only if a device that is not built here ever joins.

The identity partition holds the SSID, the Wi-Fi password, the installation CA certificate, and the
device's private key and certificate. It holds no address and no configuration. Its layout is
specified in [device firmware provisioning](device-firmware-provisioning.md).

ADR 0015's boundary applies unchanged: the partition is not encrypted, so physical possession of a
device exposes that device's secrets. Flash encryption and secure boot are rejected for the same
reasons the SD cards are unencrypted. The mitigation is authorisation, not storage.

## Coordinator changes

**Authorisation.** `PrincipalKind` gains one member per device role, and the closed
`HTTP_PERMISSIONS` table gains explicit entries for the device stream and status endpoints. No
device role receives console permissions. A device can read its own configuration stream and post
its own status, and nothing else.

**Input path.** Button events arrive as authenticated HTTPS requests rather than routed CAN frames.
This is the largest piece of work here and it is coordinator work, not firmware work:
`protocol/router.py` currently turns a `0x700` frame into a `ButtonPressed` event, and that path is
replaced rather than adapted. The kernel's single-owner semantics are unchanged.

**Live contract.** The frontend contract loses the CAN registry's device fields, including
`device_session_id`, and gains Wi-Fi device presence and status. The schema, the generated console
contract and both frontends change together. This is the second change to that contract, after the
transport swap; keeping them separate means a failure during either is unambiguous.

**Simulation.** The simulated devices in `runners/simulation/devices/` currently speak the CAN
registry. They become HTTPS clients following this contract, preserving ADR 0003's requirement that
simulation uses the production path.

## Removal

The superseded CAN protocol is deleted, not retained for possible reuse. Most of it has no consumer
once configuration moves to Wi-Fi, the frames a future CAN command path would need are stateless
and would not reuse this session-based wire format, and the firmware beneath it does not run on the
new boards. Git retains it if it is ever wanted.

The work is not complete while any of the following still exists. Removal is part of the same
change, not a follow-up.

Protocol definitions:

- `protocol/custom.toml` and `scripts/generate_custom_protocol.py`
- the generated block in `protocol/custom_ids.md`, and the registry, ISO-TP and conformance-vector
  sections of `protocol/README.md`
- `protocol/test-vectors/button-pad-program-v2.json`

Coordinator modules:

- `hosts/src/e87canbus/protocol/generated.py`, `router.py` and `servotronic_protocol.py`
- `hosts/src/e87canbus/protocol/can.py`, reduced to vehicle frame handling only
- `hosts/src/e87canbus/domain/devices/registry.py`
- `hosts/src/e87canbus/transport/isotp.py` and the `transport` package if nothing remains
- registry state in `kernel/kernel.py`, `service/diagnostics.py`, `adapters/output.py`,
  `api/models/live.py`, `api/internal/commands.py`, `config.py` (`CustomCanIds`) and
  `runners/live.py`
- `runners/simulation/devices/peer.py`, and the registry paths in `neotrellis.py`, `session.py` and
  `runtime.py`

Firmware and libraries:

- `embedded-libs/isotp_transport`, which has no future consumer once the transport is gone
- `scripts/button_pad_upload.sh` and `scripts/coordinator_panel_upload.sh`, replaced by `e87ctl`

`devices/button-pad/` and `devices/servotronic-controller/` are AVR projects built on an MCP2515
and the removed protocol. Their firmware does not survive, and it is not ported: the replacements
are ESP32 projects written against this specification, in their own later work.

Reduce each to a documentation stub rather than deleting the directory. Keep:

```text
devices/<device>/
  README.md                 what the device does, its obligations under this specification, and
                            the bench wiring that still applies
  legacy-avr-reference.md   snippets worth reading when the replacement is written
```

Delete `platformio.ini`, `src/`, `include/` and `test/`. The reference file is Markdown containing
fenced C++ rather than compilable source, so nothing builds it, lints it or mistakes it for live
code, and its name says both that it is old and which silicon it targeted.

Keep in the reference only what survives the silicon change: NeoTrellis seesaw scanning, debounce
and LED addressing; the Servotronic curve evaluation, bounds and monotonicity checks; the bounded
PWM ceiling and local failsafes; and the watchdog behaviour. Do not keep MCP2515 driver use, ISO-TP
framing, registry state machines or anything generated from `custom.toml`. A reference nobody
should copy from is worse than no reference.

`devices/README.md` currently states that each directory is an independently buildable firmware
project. Update it, since two of them will not be.

`devices/coordinator-panel/` is unaffected. It is a QT Py RP2040 with no CAN and no ISO-TP, and its
link to the Pi is its own. It stays live and untouched.

`embedded-libs/button_pad_effects` stays. Compositing feedback over a base scene is
transport-independent, independently tested, and still what the device does under this
specification. If the replacement firmware does not adopt it, delete it then.

Tests: `test_device_registry.py`, `test_isotp_transport.py`, `test_generated_protocol.py`,
`test_servotronic_protocol.py`, `test_button_pad_firmware_host.py`, which tests firmware that no
longer exists, and `test_can_protocol.py` are
deleted or reduced to vehicle decoding. Registry assertions are removed from the roughly fifteen
other suites that carry them, including `test_live.py`, `test_runtime.py`, `test_output.py`,
`test_controller_loop.py`, `test_simulation_devices.py` and `test_live_contract.py`. Do not leave a
test asserting that a removed feature is absent.

Documentation: `devices/README.md`, `protocol/README.md`, `docs/setup.md`, `docs/simulation.md`,
`docs/reliability.md` and the root `README.md` all describe the CAN handshake or ISO-TP snapshots
and are rewritten, not annotated. The ADR index records ADRs 0004, 0005, 0008 and 0012 as
superseded rather than editing them.

Verification is mechanical. After removal, `HELLO`, `WELCOME`, `HEARTBEAT`, `isotp`, `ISO-TP`,
`custom.toml`, `CustomCanIds`, `device_session_id` and `generate_custom_protocol` must not appear
outside this specification, ADR 0017 and the superseded ADRs. The contract generators must produce
no diff, and `protocol/README.md` must retain exactly one line reserving `0x700`–`0x70F` for
project devices.

## Open questions

- Whether button presses reach acceptable latency over mTLS Wi-Fi with the boards mounted where
  they will live and the engine running. If not, ADR 0017 keeps `0x700`–`0x70F` available for
  moving small command and status frames onto CAN under unchanged coordinator ownership. Measure
  p99 latency and reconnect frequency over a session before deciding.
- The configuration document type for each role, which this specification deliberately does not
  define.
