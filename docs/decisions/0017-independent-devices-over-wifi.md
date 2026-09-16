# ADR 0017: Independent devices configured over Wi-Fi

- **Status:** Proposed
- **Date:** 2026-09-16
- **Supersedes:** ADR 0004's generated custom protocol, ADR 0005's ISO-TP snapshot transport,
  ADR 0008's device registry and transport ownership, and ADR 0012's deferred cockpit
  configuration transport. ADR 0005's atomic whole-scene semantics remain in force on the new
  transport. ADR 0007's Servotronic-owned assistance mapping is strengthened, not replaced.

## Context

The original design made CAN the only link between the coordinator and project devices. Every
device registered over CAN, received configuration through bounded ISO-TP snapshots, and held no
useful behaviour of its own. That was correct when devices were thin and the coordinator was small.

Both ends have since grown. Device configuration no longer fits comfortably in 8-byte frames or
64-byte reassembled payloads, the coordinator now owns substantial per-device state, and the
planned cockpit needs more configuration than the CAN link can carry. ADR 0013 already built a
provisioned, authenticated Wi-Fi network with device identity, and ADR 0015 already provisions
certificates that name a device's installation, role and ID. The coordinator-to-device link is the
only part of the system that has not moved onto it.

Separately, every device now decodes the vehicle data it needs directly from K-CAN rather than
receiving it republished by the coordinator. That makes a device's core function independent of
the coordinator for the first time, which changes what a coordinator outage costs.

## Decision

One rule governs transport:

> CAN is the car. Devices read vehicle data from it and actuate the car on it. Wi-Fi is the only
> channel between a device and the coordinator.

Devices never communicate with each other, on any transport. A device addresses the coordinator and
nothing else and has no awareness that other project devices exist. This is a design rule rather
than a network control; the network does not prevent it and is not asked to.

Each device runs its primary function from directly decoded vehicle data and a stored configuration
document, so it operates correctly before the coordinator is reachable and continues operating if
the coordinator is lost. The coordinator owns configuration semantics and publishes one document
per device over mutually authenticated HTTPS.

The coordinator publishes state, never momentary actions. It has no channel for driving a device
effect directly, so a device's response to its own inputs, press feedback and connection
indication, is firmware behaviour rather than a remote command. Only the device can know its own
link is down, so only the device can indicate it. A device resolves locally exactly what it has
local inputs for, and everything else arrives already resolved.

There is one configuration document per device. It is stored and restored at boot, with no
field-level exceptions and no expiry, so whatever was current at power-off is what the device
starts from. This may include values that change how the car behaves, such as an elevated steering
assistance override. What makes that acceptable is that one operator configures these values and
the devices that display them restore from the same power-off, so a restored override is visible
rather than surprising. That assumption is recorded rather than enforced: earlier drafts required a
durable indication, which would have made one device's behaviour depend on another device's
configuration.

Push uses server-sent events, replacing Socket.IO in both hosts and both frontends. Every
connection begins with a complete snapshot; there is no replay, event ID or retention. Commands stay
on HTTP, because request and response semantics belong there and rebuilding them over a socket is
more code, not less. The frontend migration is sequenced first so the transport is proven in a
browser before firmware depends on it.

Configuration is keyed by device ID, which the certificate already carries alongside the role. The
role selects the document type and the device ID selects the document, so a role with several
installed devices needs no change to transport or addressing. Devices are clients: the coordinator
never initiates a connection, discovers nothing, and does no work for an absent device.

Transport and storage never parse configuration payloads. Adding a device adds a document type on
the coordinator and a parser in that device's firmware, and changes nothing in provisioning,
caching or `e87ctl`.

The CAN registry handshake, the ISO-TP snapshot transports, the generated custom protocol and their
tests, contracts and documentation are removed rather than retained for possible reuse. Identity
comes from the device certificate and presence comes from an open stream, so the registry has no
remaining consumer. Arbitration IDs `0x700`–`0x70F` stay reserved for project devices and unused.

## Consequences

- A device works correctly during access-point bring-up and through a coordinator outage. What an
  outage costs is adjustment, not function.
- The coordinator remains the single owner of every vehicle-level decision. There is no second
  authority and no reconciliation problem on recovery.
- Button events reach the kernel as authenticated HTTPS requests rather than CAN frames. This
  changes the coordinator's input path, not only firmware.
- Device configuration is no longer bounded by CAN payload sizes, and the cockpit's configuration
  question is answered without a new transport.
- The button pad's LED override channel and its compositing rules disappear, along with the
  coordinator-triggered flash they existed to carry.
- Socket.IO and Engine.IO are removed. Their bounded-queue and slow-peer rules survive, because one
  producer still fans out to independent response bodies and one blocked client must not stop the
  others; only the Engine.IO-shaped implementation goes.
- Both live channels move, the coordinator's and the console host's own local one. The shared
  adapter cannot be removed while either remains.
- The workbench's simulated CAN trace view is removed with them. Its subscribe and unsubscribe
  messages were the last client-to-server members of the live contract, so the push channel becomes
  one-way as a fact rather than as a constraint of the transport. The simulation bus keeps its own
  frame buffer, which the tests depend on.
- The live contract loses its CAN registry fields and gains Wi-Fi device presence, in a second
  change after the transport swap. The console and coordinator frontends change with it.
- Existing button-pad and Servotronic firmware does not survive. Those devices are moving from AVR
  with an MCP2515 to ESP32 with integrated TWAI, so the CAN layer beneath the removed protocol was
  being rewritten regardless.
- Wi-Fi becomes the only path for device adjustment and status. If measurement shows it cannot
  carry small frequent messages acceptably, the reserved IDs allow moving command and status frames
  back onto CAN under unchanged coordinator ownership. That would be an addition, not a redesign.
- Device-to-device communication is rejected permanently, on CAN and on Wi-Fi. It is the only
  variant that creates a second commanding authority, and it would require duplicating the assist
  model into pad firmware, a recovery reconciliation rule, and a handover timeout.
