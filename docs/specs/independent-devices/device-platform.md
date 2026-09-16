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
  "payload": "<base64, at most 8192 decoded bytes>"
}
```

`schema_version` belongs to that device role's document type and is not a global version.
`generation` is monotonic per device and increments on any change.

There is no payload digest. The document arrives over authenticated TLS, the device stores the
whole envelope as one atomically committed NVS entry, and the device's own parser rejects a payload
its schema does not accept. A digest would add machinery without adding a distinct boundary.

The coordinator publishes the document as a `configuration` event on the device's stream, so a
change reaches the device as soon as it is made. There is no polling interval and no replay. Every
connection begins with the current document, as described in
[the live event transport](live-event-transport.md).

Four rules make opacity safe:

- A document replaces the entire configuration atomically. A partial or failed write is never
  applied. This carries ADR 0005's whole-scene semantics onto the new transport.
- A device that does not recognise `schema_version` keeps its last stored document and reports the
  mismatch in its status. It never merges, migrates or guesses.
- A device bounds its `data:` line buffer and abandons a record that exceeds it, without
  attempting to decode. It cannot avoid reading bytes from an open stream, so the bound is on what
  it accumulates rather than on what arrives.
- The current authenticated document always wins, whatever its generation. A device never rejects a
  document for carrying an equal or lower generation than the one it holds. The coordinator is
  authoritative, and a counter that resets after a database restore, a reprovision or a bug must
  not leave a device permanently stuck on stale configuration. `generation` exists to let the
  coordinator recognise a no-op, not to let a device overrule its owner.

Adding a device means adding a document type on the coordinator and a parser in that device's
firmware. It changes nothing in this specification, in the configuration store, or in `e87ctl`.

## The button pad configuration document

This is the first document type defined, and it is the worked example the others follow.

The coordinator already computes this. `domain/controller/button_leds.py` takes application state
and the active profile and derives the complete desired pad scene. Nothing about that derivation
changes. What changes is that its output is serialised into a configuration document instead of
being compiled into an ISO-TP track and pushed as a CAN effect.

**One layer, reissued.** There is no base scene and no override. The coordinator regenerates the
whole document whenever anything feeding the derivation changes, bumps `generation`, and publishes
it. A button becoming unassigned is a new document, not a patch to the old one.

**Shape it against the pad, not against the old frames.** `ButtonPadTrackPayload` was sized by a
16-byte ISO-TP command and its shape exists to fit that. The document is JSON inside the envelope
and inherits none of those bounds. Do not port the track encoding.

Sixteen entries, one per button, each a complete state object:

```json
{
  "schema_version": 1,
  "buttons": [
    {"state": "assigned", "colour": [0, 0, 255], "animation": {"type": "breathe", "period_ms": 2000, "minimum": 8, "maximum": 255}},
    {"state": "unassigned", "colour": [0, 0, 0], "animation": null}
  ]
}
```

**Colour is raw RGB, already resolved.** The coordinator resolves the authored colour and the
button's current state into the exact channels the pad lights. The pad does no brightness scaling
and knows nothing about active, inactive or resting. Today's `resting_rgb` scaling stays
coordinator-side.

**Constants are named for their role, never for their value.** `SOFT_AMBER` and every other
colour-named constant goes. What remains is named for what it means: `UNASSIGNED_COLOUR`,
`UNASSIGNED_BRIGHTNESS`, `INACTIVE_BRIGHTNESS`. Authored colours are stored as RGB by the
configurator and travel as RGB, so no constant in the coordinator names a hue an operator chose.

**Animation is a name and its parameters, not a compiled track.** The document carries
`{"type": "breathe", ...}` and the pad decides how to render it. This couples the generator loosely
to the pad's repertoire, which is accepted: compiling keyframes on the coordinator would put a
renderer on the wrong side of the link and make every animation change a coordinator change. A pad
that receives a type it does not implement ignores the animation and lights the button solid in its
colour. It never rejects the document over it.

**The per-button state value travels even though the colour is already resolved.** The pad needs it
to decide local behaviour the coordinator cannot see, primarily whether a press flashes feedback at
all. An unassigned button does nothing when pressed.

**Press feedback is firmware behaviour.** Nothing about the feedback blink is in the document and
nothing about it comes from the coordinator, which is what removes the override channel described
above.

### Availability is deferred

A button whose command the car cannot currently obey renders as `UNAVAILABLE` today, in amber.
That is removed rather than carried across, and nothing replaces it in this milestone.

The design that would have replaced it had the device publish evidence in its status and the
coordinator turn that into a boolean, in one pattern shared by every device it listens to. It is a
reasonable design and it is not being built now: it is a distinct feature on top of an already large
set of changes, and the operator configuring these devices knows what is fitted. Unassigned covers
what the document actually needs today.

The consequence, so it is not discovered mid-implementation: `ButtonVisual.UNAVAILABLE`,
`BUTTON_FEEDBACK_UNAVAILABLE`, the `servotronic_usable` parameter on `derived_button_led_state` and
the `ButtonLedPresenter` seam all go.

`_servotronic_usable` in `kernel/kernel.py` goes with them, and so does everything it gates. All
four of its conditions are facts about the CAN control path: `servotronic_output_available` is
wired from `servotronic_can_control_available` in `runners/live.py`, `steering_actuator_fault` is
raised by the CAN effect executor, and the other two read the registry. None of them survives the
transport change, so nothing is left to AND. `_require_servotronic`, the steering clause in
`_gate_effects` and the `FeatureUnavailable` responses on the steering routes go with it: the
coordinator now updates configuration whether or not the device is connected, and the device
collects it when it returns. That is the behaviour this architecture is for.

## The Servotronic configuration document

The Servotronic controller is where the transport rule changes the most, because the coordinator
currently computes the answer and the device only holds it.

Today `domain/controller/steering.py` evaluates the curve against speed the coordinator decoded,
and sends the resulting assistance value as a `SetSteeringAssistance` effect on every change. The
device is a PWM output with a watchdog. Under this specification the device decodes speed from CAN
itself and evaluates its own stored curve, which makes the coordinator's evaluation both redundant
and the thing that breaks when the link drops.

So the assistance value stops travelling. What travels is everything needed to compute it:

```json
{
  "schema_version": 1,
  "mode": "auto",
  "assistance": 0.5,
  "curve": {
    "schema_version": 1,
    "points": [[0, 1000], [100, 900], [200, 780], [300, 640], [600, 420], [1000, 260], [1600, 140], [2500, 60]]
  },
  "speed_timeout_ms": 1000
}
```

`mode` is `auto` or `fixed`. In `auto` the device interpolates the curve against decoded speed. In
`fixed` it holds `assistance` and ignores speed entirely.

**The device knows nothing about steps.** `assistance` is a resolved fraction between 0 and 1.
Discrete manual levels are a coordinator and UI concern: however many steps the UI offers, step 5
of 10 travels as `0.5`. Changing the step count is then a coordinator change alone, and no device
has to be told about it.

**Maximum assistance is not a device mode.** It is `fixed` at `1.0`. Keeping it distinct on the
device would add a third mode that behaves identically to one that already exists.

Both distinctions stay coordinator-side, where they mean something. `MaximumAssistance` wraps the
previous `NormalSteering` so the toggle restores what came before, and the manual level index is
what the console's control binds to. Neither wrapper nor index travels. Every document is a
complete statement of what to do, so the device holds no toggle history and no step arithmetic.

The curve keeps the existing schema-version-1 shape: the fixed eight-point deci-kph grid with
per-mille assistance, already validated as monotonic and on-grid in `domain/steering/curves.py`.
Keeping it means the device interpolates in integers over a grid it can hold in flash, and the
coordinator's existing validation is what the device relies on rather than repeating.

`speed_timeout_ms` comes from `SteeringConfig`. It travels rather than being compiled into firmware
because the device applies the staleness rule now while the coordinator's UI presents it, and the
two must not be able to disagree. `manual_level_count` stays on the coordinator, because it is
exactly the step count the device does not need.

**The device owns the fallbacks it can observe.** Stale or never-observed speed resolves to zero
assistance, which is the car's unassisted behaviour and the same choice the coordinator makes
today. So does an unparseable or unrecognised document, except that the device keeps its last good
one. The PWM ceiling and the local watchdog stay firmware concerns and are not configurable.

`SteeringCommandReason` goes entirely. Its `AUTO`, `MANUAL` and `MAXIMUM` members annotated a
value the coordinator computed, and `CAN_READER_FAILURE`, `INBOX_OVERFLOW` and `SHUTDOWN` described
a coordinator that could no longer compute one, which is no longer something that affects
steering.

### Defaults and disconnection

The role default is `auto` with `BUILT_IN_STEERING_CURVE` from `domain/steering/curves.py`, which
is already what the database seeds. The firmware's compiled-in fallback, required of every device
by the device contract, is the same curve in the same mode. A device that has never reached the
coordinator and one that has just received its role default therefore behave identically, so first
contact changes nothing an operator could feel.

Configuration saves whether or not the controller is connected. The request is accepted, the
document is stored, the generation increments, and the device collects it when its stream returns.
There is no server-side rejection based on presence; `_require_servotronic` existed to provide one
and goes.

The console makes the consequence visible rather than preventing the action. Steering controls stay
usable, and the UI states plainly that the Servotronic controller is disconnected and that changes
are not reaching it. It has the two facts it needs already: whether the stream is open, and whether
the device's `applied_generation` matches the published one. Blocking the control instead would
mean the operator cannot prepare a setting for a device that is merely powered down, which is the
behaviour this architecture removes.

### Servotronic status

The console currently shows what the controller is doing, and it must keep showing it. That
information now arrives as status rather than as the coordinator's own projection of a command it
sent. `ObservedServotronicSnapshot` already has close to the right shape, because it was a
projection of the controller's status frame:

```json
{
  "effective_assistance": 0.64,
  "observed_speed_kph": 31.2,
  "speed_fresh": true,
  "pwm_duty": 163,
  "inhibit_reason": null
}
```

`effective_assistance` is now reported rather than commanded, which is the point: it is what the
device resolved, not what the coordinator asked for. `active_curve_source`, `active_curve_revision`
and `active_curve_crc32` go, replaced by the generation echo below. `last_command_reason` goes,
because the coordinator no longer issues commands and the device's mode is already in the
configuration the coordinator published.

`watchdog_timed_out` goes too, and it is worth saying why rather than leaving it to look like an
oversight. That watchdog's subject is the command stream: it trips when no assistance command has
arrived inside `steering_watchdog_timeout_s`, so with commands gone there is nothing left for it to
watch. `steering_watchdog_timeout_s` in `config.py` goes with it. The device's own failure modes
are already reported as `speed_fresh` and `inhibit_reason`, and the MCU watchdog that protects the
PWM output is a firmware concern that never had a wire field.

### The generation echo replaces curve activation

The curve activation handshake disappears. `SteeringCurveActivationStatus`,
`ConfigureServotronicCurve`, `ActiveSteeringCurve.activation_revision`, the CRC32 fingerprint
comparison, `_servotronic_curve_matches` and `_servotronic_config_available` all exist to answer
one question: has the device got the curve
the coordinator thinks it has.

Every device status carries `applied_generation`, the `generation` of the document it currently
holds, and that answers the same question for every role at once. The console derives what it shows
from two facts it already has: whether the device's stream is open, and whether `applied_generation`
equals the generation the coordinator last published. Pending, applied, absent. There is no
per-feature activation state machine and no second confirmation path.

This is a common status field rather than a Servotronic one. The button pad reports it too, and so
does every device added later.

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

Configuration is keyed by device ID from the start, so a role with several installed devices, a
sensor repeated in different positions, needs no change to the transport or the addressing. This is
not free. Role keying would have no orphan rows and no default-assignment behaviour, and device
keying has both. The cost is accepted because a repeated role is expected and a later migration
would have to rewrite stored configuration on a live installation.

A connecting device with no stored configuration receives its role's default document. With one
device per role that is always correct and no unconfigured state is ever visible. Assigning a
specific configuration to a specific device belongs in the console UI and is built when a role
first has more than one device, not before.

Reflashing firmware does not change the device ID. Identity lives in its own partition precisely so
firmware can be replaced without it. Only reprovisioning identity mints a new device ID, and a
device that has been reprovisioned returns with no stored configuration and receives the role
default.

Per-device configuration on the coordinator is application state of the same kind as the existing
steering profiles. It is not the device inventory ADR 0015 refuses, which is about `e87ctl` holding
a hidden database of device identity and secrets.

## Presence

Devices are HTTPS clients. The coordinator never initiates a connection to a device, broadcasts
anything, or discovers anything. An absent device costs nothing because there is no connection.

Presence is three separate things, two of which already exist:

- `DeviceRole` in `hosts/src/e87canbus/domain/devices/catalogue.py` is the vocabulary of roles the
  repository knows about. It is a compile-time constant.
- `DeviceSource`, already `physical`, `emulated` or `disabled` per composition, was intended to say
  which roles this installation has, and cannot. See "Every known role is shown" below for what
  happens to it.
- An open stream says whether a composed device is present right now. This is the only new piece
  and it replaces the CAN `HEARTBEAT` frame.

A device whose TCP connection black-holes reconnects while the coordinator still believes the
previous stream is alive, so streams are superseded rather than accumulated. The fencing rule that
makes that safe is in the device API contract below.

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

The sizes are in [device firmware provisioning](device-firmware-provisioning.md), which owns the
table because it writes to its offsets. This section says which regions exist and why.

`e87id` and `e87cfg` are separate NVS partitions rather than namespaces in one, so provisioning can
replace identity without destroying stored configuration and reflashing firmware destroys neither.
NVS provides atomic commit and wear levelling, so the store does not hand-roll slot flipping: the
whole envelope commits or none of it does.

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
device's private key and certificate. It holds no address, because the coordinator's certificate
already covers the fixed `10.42.0.1`, and no configuration.

[Device firmware provisioning](device-firmware-provisioning.md) owns its binary layout, bounds,
versioning and validation rules. Earlier drafts had each specification defer to the other, which
left the format defined nowhere and blocked workflow 05.

ADR 0015's boundary applies unchanged: the partition is not encrypted, so physical possession of a
device exposes that device's secrets. Flash encryption and secure boot are rejected for the same
reasons the SD cards are unencrypted. The mitigation is authorisation, not storage.

## Coordinator changes

**Authorisation.** One new `PrincipalKind` member, `DEVICE`, rather than one per role: every device
role has the same route permissions, and a per-role kind would duplicate `DeviceRole` and force an
authorisation change every time a role is added. The closed `HTTP_PERMISSIONS` table gains explicit
entries for the three device routes, and no device receives console permissions. The device API
contract below states the rest.

**Input path.** Button events arrive as authenticated HTTPS requests rather than routed CAN frames.
This is the largest piece of work here and it is coordinator work, not firmware work:
`protocol/router.py` currently turns a `0x700` frame into a `ButtonPressed` event, and that path is
replaced rather than adapted. The kernel's single-owner semantics are unchanged.

**Live contract.** The frontend contract loses the CAN registry's device fields, including
`device_session_id`, and gains Wi-Fi device presence and status. The schema, the generated console
contract and both frontends change together. This is the second change to that contract, after the
transport swap; keeping them separate means a failure during either is unambiguous.

**Simulation.** The simulated devices in `runners/simulation/devices/` currently speak the CAN
registry and become HTTPS clients following this contract, preserving ADR 0003's requirement that
simulation uses the production path. How they authenticate is in the device API contract below.

## The device API contract

Three endpoints and one stream. Every one of them is mutually authenticated HTTPS on the device
network, authorised through the closed `HTTP_PERMISSIONS` table.

### Authentication

`PrincipalKind` gains `DEVICE` and `Principal` gains `role`. `_console_principal` in `auth.py`
becomes `_certificate_principal`: it already loads the PEM, reads the single URI SAN, matches
`DEVICE_IDENTITY_PATTERN` and checks the installation ID. The only change is that instead of
rejecting every role but `console`, it accepts any role in `DeviceRole` and returns
`Principal(DEVICE, installation, device_id, role)`. Console keeps its own kind, because its
permissions are entirely different.

Certificates are already ECDSA P-256 (`_create_leaf` in `e87ctl/src/e87ctl/provisioning.py:338`),
which is the right choice for an ESP32 handshake and needs no change.

A device reaches its own configuration and its own status and nothing else. Scoping is by the
authenticated device ID, never by a value in the request body, so no device can name another.

### `GET /api/devices/stream`

The device's SSE stream, on the transport defined in
[the live event transport](live-event-transport.md). It carries exactly one event type:

```text
data: {"schema_version":1,"generation":42,"payload":"<base64>"}

: keepalive

```

One type per stream is the rule everywhere, not a device concession; see the live event transport.
For the device it means the firmware reader is a loop that accumulates a `data:` line and hands it
to one parser, with no event names, no dispatch table and no unknown-event handling. Anything else
the coordinator might want to tell a device belongs in the configuration document, or in a second
stream if one is ever warranted.

The current document is sent immediately on connect, as every stream does.

**Superseded streams.** The coordinator holds at most one stream per device ID, and a new
connection replaces the old one. Presence is keyed by the stream rather than by the device: each
accepted connection gets a token, and a disconnect clears presence only if the closing stream's
token is still the registered one. Without that, a black-holed connection's late disconnect clears
the presence its own replacement established.

### `POST /api/devices/status`

The device reports what it is doing. The response is `204` with no body, because there is nothing
for the device to do with one.

```json
{
  "status_version": 1,
  "applied_generation": 42,
  "configuration_error": null,
  "device": { }
}
```

The common fields are the same for every role. `applied_generation` is the generation of the
document the device currently holds, or `null` when it holds none. `configuration_error` is `null`
in normal operation and otherwise names why the last document was not applied, most importantly an
unrecognised `schema_version`, which the opacity rules require a device to report rather than guess
at.

`device` holds the role's typed status, the Servotronic body above being the worked example. This
is the asymmetry worth naming: configuration is opaque to the coordinator and typed only by the
device, while status is typed by the coordinator and acted on. They are not two instances of one
mechanism and should not be made to share one.

**There is no heartbeat.** An open stream is presence, and the coordinator learns a stream is dead
from a failed keepalive write within the keepalive interval. A status post that carries no new
information would duplicate that signal with a second staleness rule to reconcile against it. So
status is posted on change only: once when the stream opens, and thereafter whenever a reported
value changes, rate-limited to at most 5 Hz so a continuously varying value like road speed cannot
saturate the link.

The consequence is that a device's last posted status stays correct until it posts again, and
absence is shown from the stream rather than inferred from silence. Earlier drafts specified a
heartbeat interval and a staleness rule; both were removed once presence had a direct signal.

### `POST /api/devices/button-press`

```json
{"button_index": 4}
```

Responds `204`. This replaces `protocol/router.py` turning a `0x700` frame into a `ButtonPressed`
event; the kernel's single-owner semantics are untouched.

**The coordinator assigns the timestamp.** Devices send none. They have no synchronised clock, the
transit delay is one hop on a local link, and `observed_at` exists to order events inside the
kernel rather than to record wall-clock truth. This removes clock synchronisation from the device
contract entirely.

**Presses are never retried and carry no sequence number.** A lost response leaves a toggle
ambiguous, and the two ways out are an idempotency key or not retrying. Not retrying is both
simpler and more correct here: re-sending a toggle that did land inverts the operator's intent,
whereas dropping one is visible and recoverable. It is visible because the button scene is the
acknowledgement. A toggle that did not reach the kernel produces no new configuration document, the
button does not change state, and the operator presses again.

That makes press latency the round trip from press to relit button, which is the measurement
already recorded as an open question below.

**Presence does not gate it.** A device posting a press is self-evidently present. The
`_gate_effects` check that dropped button effects for an inactive pad has no subject left.

### Simulated devices

The simulated devices in `runners/simulation/devices/` become HTTPS clients of these endpoints,
which ADR 0003 requires: simulation exercises the production path.

They authenticate through the production path unchanged. `auth.py` does not verify a certificate
chain; nginx does, and the application trusts `X-E87-Client-Verify: SUCCESS` from a trusted proxy
address and parses the PEM in `X-E87-Client-Certificate` for identity. So the simulator mints a
self-signed P-256 certificate per simulated device at startup, with the correct URI SAN, and sends
the same two headers nginx would. Every line of authentication logic that runs in the car runs in
simulation, and `auth.py` gains nothing simulator-specific.

The simulator composition adds its own loopback address to `_trusted_proxy_addresses`. That is the
existing mechanism, and the live composition is not changed.

The alternatives were a real HTTPS boundary with real certificates, which means running nginx under
the simulator, and a simulator-only principal, which puts a branch inside the code ADR 0003 exists
to exercise.

### Every known role is shown

`DeviceSource` was intended to say which roles an installation has, and cannot: the closed `car` and
`bench` compositions in `deployment.py` hard-code both roles as `physical` and `DeploymentSpec`
rejects variation.

Accept that. A role appears in the UI because it is in `DeviceRole`, and adding a role to that enum
is the act of saying the installation has one. The car has one of each, a role absent from the
installation would be a role nobody had written firmware for, and an installation-composition source
is configuration for a variation that does not exist. If a second installation ever has a different
set, build it then.

## Removal

The superseded CAN protocol is deleted, not retained for possible reuse. Most of it has no consumer
once configuration moves to Wi-Fi, the frames a future CAN command path would need are stateless
and would not reuse this session-based wire format, and the firmware beneath it does not run on the
new boards. Git retains it if it is ever wanted.

The work is not complete while any of the following still exists. Removal is part of the same
change, not a follow-up.

This inventory is a guide to the areas that need looking at, not a checklist that can be worked
through and ticked off. It cannot be exhaustive. Its first draft was built by searching for protocol
symbols, which finds transport modules and misses every place the wire vocabulary was deliberately
promoted into the domain, as `domain/buttons/pad.py` did on purpose. An independent review found
that whole category afterwards. Expect the same to happen again: search for consumers of the types
as well as the modules, and treat anything the list does not name as still in scope.

Protocol definitions:

- `protocol/custom.toml` and `scripts/generate_custom_protocol.py`
- the generated block in `protocol/custom_ids.md`, and the registry, ISO-TP and conformance-vector
  sections of `protocol/README.md`
- `protocol/test-vectors/button-pad-program-v2.json`

Coordinator transport modules:

- `hosts/src/e87canbus/protocol/generated.py`, `router.py` and `servotronic_protocol.py`
- `hosts/src/e87canbus/protocol/can.py`, reduced to vehicle frame handling only
- `hosts/src/e87canbus/domain/devices/registry.py`
- `hosts/src/e87canbus/transport/isotp.py` and the `transport` package if nothing remains
- registry state in `kernel/kernel.py`, `service/diagnostics.py`, `adapters/output.py`,
  `api/models/live.py`, `api/internal/commands.py`, `config.py` (`CustomCanIds`) and
  `runners/live.py`

Application code carrying the wire vocabulary. `domain/buttons/pad.py` re-exports the CAN codec's
track types so the rest of the domain names them there, and those types reach application effects,
the controller snapshot, every state commit and the live contract. Each of these needs an explicit
replacement or deletion, not an import fix:

- `domain/buttons/pad.py`
- `domain/controller/button_leds.py`, `intents.py` and `snapshot.py`
- `domain/controller/steering.py` entirely, with `SetSteeringAssistance`, `SteeringCommandReason`,
  the `SteeringActuator` protocol and `SteeringActuatorFailure`. The device evaluates the curve
  now, so the coordinator has no assistance value to compute or send.
- the curve activation handshake: `SteeringCurveActivationStatus`, `ConfigureServotronicCurve`,
  `ActiveSteeringCurve.activation_revision`, the CRC32 comparison, `_servotronic_curve_matches`,
  `_servotronic_config_available` and the activation status in the live contract
- `_servotronic_usable`, `_require_servotronic`, `_servotronic_output_available`,
  `steering_actuator_fault` and the steering clause in `_gate_effects`
- `watchdog_timed_out` through the diagnostics and live models, and
  `SimulationConfig.steering_watchdog_timeout_s`, whose subject was the removed command stream
- device-specific effects and feedback state in `domain/events.py` and `domain/state.py`
- `kernel/inputs.py`, `kernel/health.py` and their package exports
- the Servotronic projections in `service/diagnostics.py`
- `frontend/apps/coordinator/src/hooks/use-button-pad-program.ts`
- both Servotronic availability implementations and the device-status presentation that consumes
  them, including `frontend/apps/console/src/components/car-layout/car-ui.ts`

Simulation. Deleting the registry modules alone leaves imports and generated clients broken:

- `runners/simulation/devices/peer.py`, and the registry paths in `neotrellis.py`, `session.py` and
  `runtime.py`
- `runners/simulation/devices/servotronic.py`, which subclasses the registry peer
- `runners/simulation/commands.py`, which exposes protocol-version and status-code mutations, and
  the simulator HTTP routes and models in `runners/simulation/api/routes/devices.py`
- `deployment.py` and `runners/composition.py`, which encode the registry-era role and source
  composition
- the generated OpenAPI operations and simulator frontend client code built from those routes

Dependencies and configuration:

- `can-isotp` in the root `pyproject.toml`, with the lock regenerated
- the import-linter exceptions in `pyproject.toml` that exist for the removed layering

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

Tests. Deleted or reduced to vehicle decoding: `test_device_registry.py`,
`test_isotp_transport.py`, `test_generated_protocol.py`, `test_servotronic_protocol.py`,
`test_can_protocol.py`, `test_button_pad_program_vectors.py`, and the two AVR host-compilation
suites `test_button_pad_firmware_host.py` and `test_servotronic_firmware_host.py`, which test
firmware that no longer exists. Registry and effect assertions are removed from the suites that
carry them, including `test_live.py`, `test_runtime.py`, `test_output.py`,
`test_controller_loop.py`, `test_simulation_devices.py`, `test_live_contract.py` and
`test_application_controller.py`. Do not
leave a test asserting that a removed feature is absent.

`e87ctl/tests/test_provisioning_artifacts.py` asserts `can-isotp` appears in the application
bundle and changes with the dependency. This is the one place workflow 04 writes inside `e87ctl/`,
so it is an explicit handoff rather than a violation of workflow 05's ownership.

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
- Whether button availability returns, and if so whether the device-evidence pattern described
  above is the right shape for it.
