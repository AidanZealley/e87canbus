# Coordinator and console split

- **Status:** Draft for review
- **Date:** 2026-08-10

## Summary

Move the driver-facing screen from the coordinator to a second Raspberry Pi 4 named the
**console**. The coordinator stays near the junction box and connects to K-CAN, PT-CAN and F-CAN.
The console mounts in the dashboard or centre-console area, connects receive-only to K-CAN and
connects to the coordinator over dedicated Ethernet.

This is primarily a separation of the existing system, not a new architecture:

- Pull the existing reusable Python CAN transport and protocol code into a location used by both
  Pi roles.
- Add the smallest console composition needed to read K-CAN and publish bounded connection and
  frame-activity status to its browser.
- Split the existing frontend into two conventional Vite applications with different content.
- Copy the existing Pi setup path into coordinator and console installers, then remove everything
  each role does not need. Share setup code only where the resulting duplication is substantial and
  genuinely identical.
- Add the dedicated Ethernet configuration, narrowly scoped coordinator exposure and necessary
  systemd units.

The implementation should prefer moving, deleting and composing existing code over introducing new
frameworks, layers or generic infrastructure.

## Names and scope

- **Coordinator:** Headless Pi 4 that owns control behaviour, durable settings, diagnostics and the
  authoritative HTTP and Socket.IO APIs.
- **Console:** Driver-facing Pi 4 that owns the screen, local K-CAN observation and driver UI.

`Console` describes the module's current physical role and leaves `cockpit` available for a possible
future full digital instrument-cluster replacement.

The screen may continue changing. The console frontend remains responsive, while screen choice,
layout adaptation, mounting and touchscreen configuration remain ordinary hardware and UI work
rather than architectural decisions.

## Resulting system

```text
Console Pi 4                                Coordinator Pi 4
------------                                ----------------
Console frontend                            Coordinator frontend
Small local CAN activity slice              Existing API and controller
K-CAN, receive-only                         K-CAN + PT-CAN + F-CAN
      |                                             |
      +---------------- K-CAN ----------------------+
      |                                             |
      +--------- dedicated Ethernet ----------------+
                  HTTP + Socket.IO
```

The junction box makes the vehicle information currently needed by accessory devices available on
K-CAN. The coordinator retains all three direct bus connections for more detailed data and future
bus-specific behaviour. The console and other accessory devices need only K-CAN unless a later,
evidence-backed requirement changes that decision.

## Responsibilities

### Coordinator

The coordinator continues to own:

- The controller kernel and all vehicle-control decisions.
- Every CAN transmit capability.
- Durable settings and profiles.
- Coordinator health and diagnostics.
- Semantic HTTP commands and authoritative Socket.IO state.
- Hotspot management and the coordinator status panel.

Moving the screen must not change these behaviours. The coordinator must remain fully operational
when the console is absent or failed.

### Console

The console owns:

- Its locally hosted frontend, kiosk and touchscreen.
- A receive-only K-CAN connection.
- Local K-CAN connection and frame-activity status.
- Connections to the coordinator's existing HTTP and Socket.IO APIs.

The console may call semantic coordinator commands. It does not duplicate coordinator control
logic, durable state or CAN output.

No decoded K-CAN signal or K-CAN-driven product feature is part of this work. The console publishes
only enough local status to prove the receive-only CAN, Socket.IO and React path end to end. When a
vehicle signal is added later, its observation will come from the console's K-CAN connection while
coordinator state will continue to come from the coordinator. The console must not silently
arbitrate between duplicate copies of the same value.

## Minimal backend change

The current code already has transport-neutral CAN frame types, narrow receiver/transmitter
interfaces and a SocketCAN adapter. These are modular internally but live under the
`coordinator/src` directory. Verified BMW codecs will also be useful to both roles.

Make those existing pieces role-neutral so the same installed Python code is used on both Pis. Do
not create a separate shared library repository, generic CAN daemon, plugin system or IPC protocol.

Rename the current top-level `coordinator` Python project to `hosts`. This directory contains code
for full Linux host computers, while the existing top-level `devices` directory remains for focused
microcontroller firmware:

```text
hosts/
├── src/e87canbus/
│   ├── console/      # Small console-specific composition
│   ├── adapters/     # Shared hardware and OS adapters
│   ├── protocol/     # Shared wire types and future verified BMW codecs
│   ├── kernel/       # Existing coordinator control kernel
│   ├── service/      # Existing coordinator service lifecycle
│   └── ...
└── tests/
    ├── console/
    └── ...

devices/
├── button-pad/
├── coordinator-panel/
└── servotronic-controller/
```

The layout is an ownership distinction, not a reason to reorganize every existing Python module.
Coordinator code remains where its current dependency layers place it; only new console-specific
code needs a `console` namespace. Console frontend and deployment files remain with their existing
concerns under `frontend/apps/console`, `deploy` and `scripts` rather than creating another top-level
console directory.

The coordinator keeps its existing runtime and failure policy. The console adds only the code it
needs to open, read, monitor and close its K-CAN interface safely, retain its connection state and
received-frame count, and publish a complete `console.snapshot` at a bounded rate. The React proof
is a small status display such as K-CAN connection state and frames received. It does not add
speculative vehicle signals or expose arbitration IDs and payload bytes.

The console snapshot follows the useful parts of the existing live pattern: a versioned envelope,
boot ID, revision, complete snapshot on connection, generated TypeScript type, one application-owned
Socket.IO transport and one path into a small Zustand store. Because every console activity event
is a complete snapshot, the proof slice does not need coordinator topic revisions, incremental
topic events, trace subscriptions, resource invalidation or resynchronization machinery. Frame
activity is coalesced, initially to no more than one publication per second.

When the first verified console signal is implemented later, the intended direct path is:

1. Read and timestamp K-CAN frames through the shared SocketCAN adapter.
2. Decode selected frames through shared, pure BMW codecs.
3. Retain a bounded current projection with signal staleness.
4. Publish that projection to the locally hosted frontend using the existing Socket.IO approach.

That later path should reuse existing lifecycle, API and live-publication code where it fits
directly. It must not generalize coordinator and console behaviour behind a new framework. The
coordinator and console queueing and failure policies may remain different. Raw CAN frames must not
become a browser API.

The console receives only a CAN receiver capability. Its SocketCAN interface is also configured in
kernel-level listen-only mode. The unused channel on its two-channel HAT remains disconnected and
has no enabled interface service.

BMW decoding remains capture-backed and network-specific. This work does not introduce unverified
IDs or promote simulator messages into physical protocol.

## Minimal frontend change

Turn `frontend` into a plain pnpm workspace containing two Vite applications:

```text
frontend/
├── apps/
│   ├── coordinator/
│   └── console/
├── packages/
│   └── coordinator-client/  # generated HTTP and Socket.IO contracts used by both apps
├── package.json
├── pnpm-lock.yaml
└── pnpm-workspace.yaml
```

The applications should use the same ordinary React/Vite structure and tooling. They differ in
content and deployment:

- The coordinator app contains configuration, diagnostics, profiles, simulation and development
  screens.
- The console app contains driver-facing telemetry, operational controls and suitable in-car
  settings.

The initial split is mechanical: existing `/car` UI moves to the console app, while existing `/dev`
and coordinator-management UI move to the coordinator app. Future changes to either application's
content are normal product work and do not need to be classified by this infrastructure spec.

Move existing routes and components to their owning application. Do not create a frontend platform,
micro-frontend system, runtime extension mechanism or generalized application shell. Do not create
a shared design-system package.
The exisiting `/` route that links to the two individual sections will beredundant and can be removed.

The console frontend has two explicit connections: local Socket.IO for the complete K-CAN activity
snapshot, and coordinator HTTP and Socket.IO over Ethernet. Copy and trim the existing singleton
transport and Zustand ingestion pattern for the local snapshot rather than sharing or generalizing
the coordinator's multi-topic live store. Raw CAN frames are never decoded in React.
Coordinator-backed controls become unavailable when Ethernet is lost and are not queued for later
replay.

## Setup and deployment

Replace the single Pi setup entry point with:

```text
scripts/setup_coordinator.sh
scripts/setup_console.sh
```

Start from the existing working setup script for both roles and trim each copy:

- Coordinator setup retains three CAN interfaces, controller/API services, persistence, hotspot,
  coordinator panel and headless operation. It removes the local screen and kiosk stack.
- Console setup retains the display, touchscreen and kiosk setup, configures one listen-only K-CAN
  interface and installs the small local console service. It omits coordinator control,
  persistence, hotspot, panel and the other CAN interfaces.

A small shared shell helper is acceptable for operations that remain meaningfully identical after
the split. Avoid building a role-driven installation framework or extracting one-line helpers.

Both scripts retain the current validate-before-start behaviour for their own expected hardware.
`Coordinator` and `console` are host roles, not additional `car`, `bench` or `simulator` controller
profiles.

## Dedicated Ethernet

The Ethernet link is the main new infrastructure:

- Use fixed addresses on a private point-to-point subnet with no gateway or DNS dependency.
- Do not enable IP forwarding or internet sharing.
- Keep the coordinator application bound to loopback.
- Add a narrowly bound proxy on the coordinator's console-facing Ethernet address, following the
  existing hotspot proxy pattern.
- Allow only the fixed console frontend origin in addition to approved development origins.
- Keep the console's local frontend and local CAN publication bound to loopback.

Use subnet `10.43.0.0/30`, with `10.43.0.1` for the coordinator and `10.43.0.2` for the console.
The link has no gateway.

Add only the systemd and network configuration required for the two resulting deployments. Existing
units should be moved or trimmed where possible rather than wrapped in replacement layers.

## Documentation

Update repository documentation alongside the implementation. At minimum, keep the root README,
project context, deployment runbooks, wiring notes, architecture descriptions and referenced file
paths synchronized with the coordinator/console split. Document both blank-Pi setup paths, the
dedicated Ethernet link, receive-only console K-CAN, frontend ownership and the new `hosts`
directory. Remove or replace instructions and diagrams that still describe one Pi hosting both the
controller and driver screen. Record accepted long-lived architectural decisions in ADRs where they
supersede or extend an existing decision.

## Failure behaviour

- Console failure or disconnection does not affect coordinator health, timing or control.
- Coordinator or Ethernet failure clearly marks coordinator-backed state and controls unavailable.
- K-CAN failure is reported by the console without affecting the coordinator connection.
- Reconnection starts from a current snapshot and never replays queued commands.
- Console queues and retained state remain bounded.
- Existing conservative coordinator failure behaviour remains unchanged.

## Hardware constraints

- Both machines are Raspberry Pi 4s.
- The console uses one channel of a
  [Waveshare 2-CH CAN HAT+](https://www.waveshare.com/2-ch-can-hat-plus.htm). Its second channel is
  unused.
- Console power currently relies on the body harness being fused at the vehicle fusebox and the
  HAT's documented 7–36 V power input.
- This spec does not claim the HAT power input is qualified for automotive reverse-battery,
  cranking or load-dump transients. Reviewing or adding branch fusing, reverse-polarity protection
  or an automotive-rated input protection stage is separate future hardware work.
- Confirm that the HAT can supply the combined peak demand of the Pi 4 and selected screen before
  installation.
- Confirm termination, transceiver compatibility, grounding and K-CAN branch wiring before vehicle
  connection.
- Leave the HAT's switchable 120-ohm termination disabled when connecting to the already terminated
  vehicle K-CAN.
- Avoid unsafe simultaneous USB and HAT power during setup and service.

## Explicit complexity constraints

This work must not introduce any of the following without revising this specification with a
concrete reason the direct approach is insufficient:

- A generic multi-role runtime or service framework.
- A standalone CAN daemon or raw-CAN network API.
- A plugin, extension or dynamic configuration system.
- A micro-frontend architecture.
- A generic deployment framework or matrix of combinable host roles.
- Shared packages containing code used by only one application.
- Duplicate BMW decoders, API contracts or authoritative state.
- Console CAN transmission, even behind a disabled feature flag.

Before completion, perform a simplification pass: remove obsolete combined-frontend routes,
coordinator kiosk files, compatibility aliases, unused services and abstractions that only support
hypothetical future roles. The same pass must remove stale documentation, commands, paths and
diagrams rather than leaving the old deployment described as an alternative.

## Completion criteria

- The coordinator runs headless with its existing controller behaviour and all three CAN networks.
- The console boots its locally hosted driver frontend and reads K-CAN in listen-only mode.
- The same SocketCAN adapter and frame types are used by both roles; later verified BMW codecs have
  one shared implementation when introduced.
- Coordinator and console frontends build independently from the pnpm workspace.
- A received K-CAN frame changes the bounded local `console.snapshot`, reaches the console Zustand
  store through Socket.IO and updates the K-CAN activity status in React.
- The console can open and continuously receive from K-CAN without depending on Ethernet or the
  coordinator.
- The coordinator API is exposed only on loopback, the hotspot address and the exact console-link
  address through constrained proxies.
- The two trimmed setup scripts can configure blank Pi 4 installations and validate their expected
  hardware before starting services.
- The unused console CAN controller is disconnected and inactive.
- Maintained documentation describes the resulting host layout, separate setup paths, wiring,
  networking, services and frontend ownership without stale combined-role instructions.
- No obsolete combined-role deployment or frontend machinery remains unless it protects an
  explicitly documented migration boundary.
