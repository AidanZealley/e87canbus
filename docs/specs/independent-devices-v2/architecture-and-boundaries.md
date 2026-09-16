# Independent devices: architecture and boundaries

- **Status:** Approved
- **Date:** 2026-09-16

## Purpose

Project devices stop using the repository-owned CAN protocol and become independent clients on the
existing provisioned Wi-Fi network. This document defines the result and its boundaries. It does not
divide the work into implementation workflows.

## Goals

### 1. Devices operate without the coordinator

A device performs its primary function from local inputs, vehicle data decoded directly from CAN,
and its last stored configuration. It does not wait for Wi-Fi during boot and continues operating
when the coordinator is unavailable.

The button pad is the exception inherent in its function: it can scan buttons, render its stored
scene and provide local press feedback while offline, but its presses cannot control coordinator-owned
application state until the coordinator returns.

### 2. CAN is only the car

CAN carries vehicle observations and vehicle actuation. It does not carry device discovery,
configuration, status, or coordinator commands.

The generated custom protocol, CAN device registry and ISO-TP configuration transport are removed
after their final device consumer has migrated. Device roles may migrate one at a time. An unmigrated
role may keep its old CAN path temporarily, but no new feature extends that path.

### 3. The coordinator owns device configuration

The coordinator derives one complete configuration document for each device. It sends the current
document when the device connects and sends a replacement immediately after the desired
configuration changes.

The device validates the whole document, applies it atomically and stores it for its next boot. A
partial or invalid document never replaces the last good one. Configuration has no lease, expiry or
field-level persistence exceptions.

### 4. Devices use authenticated HTTPS for coordinator communication

Server-to-client updates use server-sent events. Device inputs and status use ordinary HTTP
requests. A device never accepts an inbound network connection.

The client certificate identifies the installation, role and device ID. The coordinator derives
authorization and configuration addressing from that identity rather than trusting request data.
Role-specific authorization still applies after a certificate has been accepted. Only a button-pad
identity may submit a button press.

Devices do not communicate with each other on Wi-Fi or CAN. The access point does not enforce that
rule. It remains a software boundary.

### 5. `e87ctl` builds and provisions device firmware

Firmware is a reproducible, secret-free artifact that can be bench-tested before installation.
Provisioning combines that artifact with installation Wi-Fi credentials and a newly issued device
identity, then writes both over a physical serial connection.

Firmware, identity and stored configuration occupy separate flash regions. Reflashing firmware
preserves identity and configuration. Full provisioning replaces identity, clears stored
configuration and creates a new device ID, so the device starts from its compiled default until the
coordinator supplies the role default.

The button pad and Servotronic controller use the selected
[WeAct CAN485 ESP32 board](../../weact-can485-esp32.md). Their firmware remains role-specific.

### 6. Server push uses one simple typed mechanism

Socket.IO and Engine.IO are replaced with SSE. Commands remain HTTP.

Each client holds one stream to each host it consumes:

- a browser holds one multiplexed coordinator stream;
- the console browser holds one separate stream to the console host; and
- a device holds one configuration-only stream to the coordinator.

FastAPI models produce the OpenAPI documents. Hey API generates browser clients, TypeScript types
and Zod validators from those documents. There is no separate live-contract schema or generator.

## Transport boundaries

| Direction | Transport | Contents |
|---|---|---|
| Coordinator to browser | One multiplexed SSE stream | Current live state and resource invalidations |
| Console host to its browser | One SSE stream | Complete local console state |
| Coordinator to device | One SSE stream | Complete configuration documents |
| Browser to host | HTTP | Commands and durable resource operations |
| Device to coordinator | HTTP | Button presses and last reported status |
| Device and vehicle | CAN | Vehicle observations and actuation only |

Sharing SSE does not make these streams one contract. Browser events form a discriminated union.
Each device stream carries only the configuration type for the authenticated role.

## Configuration rules

Configuration is typed JSON. It is not base64 encoded and does not carry a separate digest. TLS
protects it in transit, the device validates its schema, and NVS commits the accepted document
atomically.

Each role document owns one `schema_version`. The surrounding delivery envelope does not repeat it.
A generation number identifies the coordinator's current stored revision. It is a non-negative JSON
safe integer, persists in the coordinator database and advances only when the desired configuration
changes. Opening a stream, reconnecting, restarting the coordinator and starting another drive do
not advance or reset it. The maximum value is `9007199254740991`; the coordinator rejects a change
rather than wrapping if that unreachable limit is exhausted.

The device reports the generation it applied, but it does not use generations to reject an
authenticated document. This allows a restored coordinator database to replace a newer local
value. Before writing flash, the device compares the complete validated document with its stored
value and skips an identical write.

The coordinator supplies a safe role default when it has no document for a device ID. Firmware also
contains a safe default so first boot does not depend on the network.

## Device addressing and discovery

The existing certificate URI SAN remains the authoritative identity:

```text
urn:e87canbus:device:v1:<installation>:<role>:<device-id>
```

Devices obtain addresses by DHCP and connect to the coordinator at `10.42.0.1`. The coordinator
stores configuration by authenticated device ID. Adding another device of an existing role does not
change the transport.

There is no application presence protocol. Devices send no heartbeat and the coordinator does not
infer presence from an SSE socket.

For diagnostics, "on Wi-Fi" means that the access point currently reports the device as an
associated station. The admin application reads that association data on demand. It may enrich a
station with its current dnsmasq lease. DHCP leases and ARP entries alone do not establish presence.

Firmware uses a diagnostic DHCP hostname derived from its certificate identity:

```text
e87-<role>-<device-id>
```

The hostname is display data, not identity or authority.

## UI ownership

The driving console does not show a connected-devices page or CAN registry diagnostics. It shows
only vehicle controls and operational state useful while driving.

The coordinator admin application owns device diagnostics. It presents a generic list rather than
one component per role. The list may show current Wi-Fi association, published and applied
configuration generations, and last reported status. "On Wi-Fi" does not claim that device firmware
is healthy. Stored status is labelled as last reported rather than current.

## Role-specific behavior

The generic platform stops at delivery, identity, persistence and authorization. Configuration and
status remain role-specific.

The button pad receives a complete desired LED scene. Its first ESP32 firmware includes a bounded,
listen-only K-CAN receive path, but does not interpret vehicle frames. Headlight-driven local
dimming waits for a capture-backed signal definition. The pad sends button indexes to the
coordinator and handles immediate press feedback locally.

The Servotronic controller receives the curve and mode needed to calculate assistance from locally
decoded speed. In fixed mode it receives one assistance fraction from `0.0` to `1.0`. The UI and
coordinator may expose any number of manual steps and resolve the selected step to that fraction.
The device does not know the step count. Maximum assistance is fixed mode at `1.0`.

The cockpit is not part of the first delivery. It can use the same device rules when its hardware
and configuration contract are ready.

## Explicit non-goals

This work does not add:

- device-to-device communication or a degraded CAN fallback;
- network firmware update, credential rotation or per-device revocation;
- flash encryption or secure boot;
- an `e87ctl` device inventory;
- configuration expiry or leases;
- a required cross-device indication of stored vehicle-affecting state;
- access-point client isolation;
- a UI for assigning different configurations to several devices of one role; or
- cockpit firmware or configuration.

Space may be reserved for a second application image, but this work does not implement OTA updates.

## Scope

These three approved documents define the target behavior. They do not define implementation order.
The next planning step divides the work into vertical slices.
