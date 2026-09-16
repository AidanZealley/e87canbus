# Independent devices

Devices become independent, coordinator-configured peers on Wi-Fi, and CAN stops being a project
bus and becomes only the car.

Recorded as [ADR 0017](../../decisions/0017-independent-devices-over-wifi.md) and described by three
specifications:

- [live-event-transport.md](live-event-transport.md) replaces Socket.IO with server-sent events.
- [device-platform.md](device-platform.md) defines how a device operates, stores configuration and
  talks to the coordinator, and removes the superseded CAN protocol.
- [device-firmware-provisioning.md](device-firmware-provisioning.md) extends `e87ctl` to build and
  provision ESP32 firmware.

The change set is large enough that it becomes six workflows rather than one. A workflow draws on
whichever specifications it needs, so the relationship is not one to one.

## How this works

This file is the durable state for the whole effort. The specifications describe the target; this
file tracks which parts of it exist yet. Nothing else is required to pick the work up.

Workflows are created one at a time, not up front. When one finishes, the next is created with
`create-agent-workflow`, producing its own folder beside this file containing the task packets a
fresh orchestration agent executes. Creating all six in advance would mean rewriting the later ones
every time a decision moved, and `create-agent-workflow` itself declines to generate a workflow
whose behaviour and boundaries are not settled.

To pick up this effort with no other context:

1. Read the three specifications and the status table below.
2. Read the most recently completed workflow's folder. That is the record of what was actually
   built, which may differ from what its packets planned.
3. **If implementation diverged from a specification, update the specification first.** The specs
   are what roll forward; workflow folders are disposable. Skipping this is the one failure mode
   that compounds, because the next workflow is then generated from a description of a system that
   no longer exists.
4. Create the next workflow.

The specifications deliberately record rejected alternatives and the reasoning behind them, not
just conclusions. The persistence section explains why there is no indication requirement; the
network section explains why there is no access-point client isolation. Without those, a later pass
proposes both again.

## Workflows

| # | Workflow | Draws on | Status |
|---|---|---|---|
| 01 | Remove the live CAN trace | transport | Ready |
| 02 | Replace Socket.IO with SSE | transport | Ready |
| 03 | Coordinator device API | platform | Ready |
| 04 | Input cutover and CAN protocol removal | platform | Ready |
| 05 | Firmware build and provisioning | provisioning | Ready, after the board prerequisite |
| 06 | Link probe firmware | platform, provisioning | Ready, after the board prerequisite |

## Prerequisite

Every design question an independent review raised is now answered in the specifications: the
device API contract, what becomes a configuration document for both devices, the identity partition
format, and whether every known role is always shown. All six workflows can be created.

One prerequisite is not a design question and cannot be resolved from the repository. Confirm the
chip, module and flash size on one of the new boards with `esptool.py flash_id`. The partition table
in device-firmware-provisioning fixes every partition but the two OTA slots, whose size follows the
confirmed flash. This is the only decision in this effort that cannot be revised later without
physically erasing every provisioned device, so it gates workflows 05 and 06.

01 through 04 are strictly sequential. 05 runs alongside 03 and 04 and owns `e87ctl/`, which
neither writes. 06 needs both 04 and 05.

```text
01 ── 02 ── 03 ── 04 ──┐
                       ├── 06
           05 ─────────┘
```

## Scope per workflow

**01 Remove the live CAN trace.** Delete the workbench's simulated CAN trace view; nothing replaces
it. First because its subscribe and unsubscribe messages are the last client-to-server members of
the live contract, so 02 inherits a contract that is already one-way. Do not touch
`runners/simulation/bus.py`: that buffer is the simulation suite's observation point for
transmitted frames and removing it would gut those tests.

**02 Replace Socket.IO with SSE.** Payloads stay identical, so any failure is a transport failure
and not a payload one. No devices involved, so the transport is proven in a browser first. Ends
with `client_to_server_event`, the snapshot event and the protocol version numbers gone entirely.

Covers both live channels. The console host has its own Socket.IO server and its own browser
transport, and the shared adapter cannot be removed while either remains. Every connection begins
with a snapshot; there is no replay to build.

One stream per `StateTopic` rather than one multiplexed channel, which is what lets the bespoke
live contract pipeline be deleted rather than ported: eight endpoints returning one type each are
ordinary OpenAPI routes, so both channels get generated types and generated Zod validators from the
document that already describes the HTTP API. Enabling HTTP/2 in nginx is a prerequisite, not a
tuning choice; without it eight streams exhaust the browser's six-connection budget and block
ordinary API requests.

**03 Coordinator device API.** The device stream, status endpoint, per-device-ID configuration
storage, a `PrincipalKind` per device role, and the simulated devices converted to HTTPS clients.
Nothing is removed. Those simulated clients matter more than they look: after 04 there is no
physical device until 06, so they are the only source of button events and keep the system
exercisable throughout.

**04 Input cutover and CAN protocol removal.** The largest workflow. Button events move onto HTTP,
then the entire CAN device protocol is deleted, the two AVR firmware projects reduce to
documentation stubs, and device presence appears in both frontends. Move ADR 0017 to Accepted when
this lands, since that is the point the decision stops being reversible.

Draw its workstreams by area, backend and contract and frontend, not as "cut over" then "delete".
Each workstream is separately accepted, so that second seam produces an accepted state containing a
complete dead input path, which is the residue the specification exists to prevent. The cutover and
the removal it makes possible belong in the same workstream.

**05 Firmware build and provisioning.** Owns `e87ctl/`, with one exception: workflow 04 edits
`e87ctl/tests/test_provisioning_artifacts.py`, which asserts `can-isotp` appears in the application
bundle and must change when that dependency is removed. That is an explicit handoff, not shared
ownership. Otherwise 05 reads `DeviceRole` from `hosts/` and writes nothing there.

Gated on the board prerequisite and on the identity partition format, not on 03 or 04. It is the
only workflow whose inputs come from outside the codebase, which is an argument for doing it sooner
rather than last.

**06 Link probe firmware.** One minimal ESP32 firmware provisioned as `button-pad`, chosen because
it is the easiest device to bench test. It joins, authenticates, holds its stream and posts status.
No CAN, no configuration parsing, no LED output. It grows into the real button pad later rather
than being replaced, so no throwaway device role is created.

If 01 to 05 are complete, 06 adds no coordinator code and no frontend code and the device simply
appears. Writing application code during 06 is a finding about 03 or 04 rather than scope for 06.

## Deliberately not specified

These were considered during design and rejected or deferred. They are decisions, not gaps. Each
line says where the reasoning lives. Disagreement is welcome; proposing one of these as though it
were an oversight is not.

- **Configuration expiry or leases.** Configuration persists across power cycles with no expiry and
  no field-level exceptions, including an elevated steering assistance override. Two mechanisms were
  designed and removed. See device-platform, "Persistence".
- **A required indication for vehicle-affecting stored state.** Removed because it coupled one
  device's behaviour to another device's configuration. Same section.
- **Access-point client isolation.** Nothing on the network stops devices reaching each other; the
  rule against it is a design rule. See device-platform, "Network membership and identity".
- **Flash encryption, secure boot, and encrypted identity partitions.** Rejected for the reasons the
  SD cards are unencrypted. Same section, and ADR 0015.
- **A device inventory, credential rotation, or per-device revocation.** Refused by ADR 0015 and
  unchanged here.
- **Network firmware update.** Out of scope, though partition space is reserved so that adding it
  later does not require erasing every device. See device-platform, "Flash layout".
- **A UI for assigning configuration to a specific device.** Deferred until a role has more than one
  device. See device-platform, "Device addressing".
- **SSE replay and event IDs.** Every connection begins with a complete snapshot instead. Removed
  after review showed replay bought nothing, since every topic is already a complete value. See
  live-event-transport, "Every connection begins with a snapshot".
- **A configuration payload digest.** TLS, atomic NVS commit and the device's own schema check
  already cover it. See device-platform, "Configuration".
- **A `PrincipalKind` per device role.** One `DEVICE` kind carries the authenticated role and ID.
  See device-platform, "Coordinator changes".
- **Multi-target firmware manifests.** The chip appears once, not per flash entry, until a
  two-chip board is actually selected. See device-firmware-provisioning, "Firmware manifest".
- **Button availability.** A button whose command the car cannot currently obey no longer renders
  differently. The device-evidence design that would have replaced the current `UNAVAILABLE` visual
  is described and deferred, not rejected on merit. See device-platform, "Availability is deferred".
- **Compiled animations in the button pad document.** The coordinator sends an animation type and
  its parameters; the pad renders it and ignores a type it does not implement. Same section.
- **Discrete manual assistance steps on the device.** The Servotronic document carries a resolved
  fraction between 0 and 1; step counts stay a coordinator and UI concern. Maximum assistance is
  `fixed` at `1.0`, not a third mode. See device-platform, "The Servotronic configuration document".
- **Presence gating on configuration writes.** Configuration saves whether or not the device is
  connected, and the UI says it is not reaching the device. `_require_servotronic` provided the
  server-side rejection and is removed. See device-platform, "Defaults and disconnection".
- **A device status heartbeat and staleness rule.** An open stream is presence, and status is
  posted on change only, rate-limited to 5 Hz. Both were specified and removed once presence had a
  direct signal. See device-platform, "POST /api/devices/status".
- **Button press retries, sequence numbers and idempotency keys.** A press is never retried. The
  relit button is the acknowledgement, so a dropped press is visible and recoverable while a
  re-sent toggle is not. See device-platform, "POST /api/devices/button-press".
- **Device-supplied timestamps and clock synchronisation.** The coordinator stamps presses on
  receipt. Same section.
- **A real installation-composition source.** A role appears because it is in `DeviceRole`.
  `DeviceSource` and `DeploymentSpec` are not extended. See device-platform, "Every known role is
  shown".
- **A hand-rolled identity partition layout, and firmware-side certificate chain, key-pair or
  validity checks.** The partition is NVS, and the TLS handshake tests what the coordinator needs
  convinced of. See device-firmware-provisioning, "Identity partition format".
- **A bespoke live contract pipeline, and a live protocol version number.** Both channels are
  described in OpenAPI and generated by `@hey-api/openapi-ts` alongside the HTTP API. The
  four-stage JSON Schema pipeline, `json-schema-to-typescript`, `live_contract.py` and the three
  protocol version constants go. See live-event-transport, "Contracts".
- **A multiplexed live channel.** One stream per topic, each carrying one type, so there is no
  event name on the wire, no union and no discriminant. The Socket.IO shape was carried over in an
  earlier draft and removed. See live-event-transport, "This replaces multiplexing, deliberately".
- **Device-to-device communication on any transport, and any CAN fallback for degraded operation.**
  Rejected permanently as the only variant creating a second commanding authority. See ADR 0017.
- **Frame visibility in the simulator.** Lost with the trace view and accepted. See
  live-event-transport, "The live CAN trace is removed".

This list grows as further calls are made. [review-prompt.md](review-prompt.md) carries the same
list for independent review, and the two should be kept in step.

## Rules every workflow inherits

Removal is part of the change that makes something obsolete, not a follow-up. No workflow leaves a
test asserting that a removed feature is absent.

**The removal inventories are a guide, not a checklist.** They name the areas of the codebase that
need looking at. They cannot be exhaustive: the first draft was built by searching for protocol
symbols and missed every place the wire vocabulary had been promoted into the domain, which an
independent review then found. An implementation agent that deletes exactly what is listed and
stops has not finished. Search for consumers of the types as well as the modules, and expect to
find things the list does not name.

## When this is done

Update the status column as workflows land. On completion, remove the generated workflow folders,
keep the three specifications, and leave ADR 0017 as the durable record.
