# ISO-TP transport and RGB virtual button pad

**Status:** Approved, two-phase implementation design.

This is the authoritative plan for replacing the provisional indexed button-pad
LED snapshot with full RGB output, first through the simulator and virtual
button pad. It deliberately keeps the feature small: two phases, one canonical
RGB state, one transport, and no physical LED rendering yet.

## Goal

Give repository-owned CAN devices a bounded ISO-TP transport for payloads that
do not fit in one classic CAN frame. Its first and only application in this
plan is an atomic 16-key RGB snapshot sent from the coordinator to the
simulated button pad and rendered by the existing browser workbench.

The same C++ transport wrapper must compile into the Arduino Micro button-pad
firmware, but neither phase claims physical NeoTrellis output or vehicle
readiness.

## Non-goals

These phases do **not** add:

- an application-level acknowledgement, read receipt, retry protocol, or
  capability negotiation;
- an effect language, device-side animation, gradients, brightness controls,
  or a generic application-PDU envelope;
- a TypeScript ISO-TP implementation or a browser CAN endpoint;
- physical NeoTrellis scanning, `Adafruit_Seesaw`, RGB rendering, current
  limiting, or bench/in-car validation;
- CAN FD, J1939 TP, UDS, arbitrary ECU communication, dynamic devices, or
  multiple instances of a role;
- transport configuration switches, queues, or a framework for hypothetical
  future devices.

The existing browser remains an HTTP/Socket.IO client. The Python simulated
button pad is the virtual CAN endpoint.

## Settled design

### Scope and ownership

Classic ISO-TP (ISO 15765-2) is the only multi-frame transport. It is a
point-to-point, opaque byte transport beneath device application code. Direct
CAN frames remain the only mechanism for button events, registration, and
heartbeats.

One link has one transmit state and one receive state. A link may transfer one
PDU in each direction at the same time; it must never interleave two PDUs in
the same direction. A send attempted while that direction is active returns
`busy`; the initial implementation does not queue or silently replace it.

Each receive side owns one fixed 256-byte buffer. It rejects a declared larger
payload, malformed frame, bad consecutive-frame sequence, or timeout, clears
the partial transfer, and never exposes partial bytes to application code.
ISO-TP Flow Control is required transport mechanics, not a receipt that an
application read, rendered, or applied a command.

The controller and Python simulator use the pinned `can-isotp` dependency
through thin project adapters. Firmware uses the pinned MIT-licensed
[`isotp-c`](https://github.com/SimonCahill/isotp-c) source through one
repository-owned C++ wrapper. Pin `isotp-c` to commit
`b2fb084aadfed6e36a97a3e67282d2777fdad0d3` (the `v1.6.1` release) and
`can-isotp` to `2.0.7`; record licence attribution with the dependency.

The wrapper is a local PlatformIO library usable by future device projects. It
owns only buffer sizing, ISO-TP setup, CAN-frame/time callbacks, and completed
payload delivery. It must not know about MCP2515, NeoTrellis, RGB, effects, or
React.

### Provisional CAN IDs

All IDs remain standard 11-bit K-CAN IDs, simulation/bench only, and require a
named collision-validation capture before in-car transmission.

| ID | Direction | Use |
|---|---|---|
| `0x708` | Coordinator → button pad | ISO-TP link data and Flow Control |
| `0x709` | Button pad → coordinator | ISO-TP link data and Flow Control |

The generated custom-protocol source remains the sole owner of these IDs and
the 256-byte limit. Do not teach the existing fixed-message generator to
describe ISO-TP frame bytes; ISO-TP owns those bytes. Generate only the link
constants and documentation from the source protocol definition.

Future devices may be assigned their own validated RX/TX pair and instantiate
the same wrapper. This plan assigns no range or dynamic allocation scheme.

### RGB snapshot PDU

Phase 2 defines exactly one application payload on the coordinator-to-pad
link: 48 bytes, in logical button order `0` through `15`, each as unsigned
eight-bit `red`, `green`, then `blue`.

```text
byte 0..2    key 0: R G B
byte 3..5    key 1: R G B
...
byte 45..47  key 15: R G B
```

There is deliberately no PDU type, effect identifier, alpha byte, or receipt.
The 48-byte size identifies this sole phase-2 payload. A complete snapshot
replaces all 16 canonical RGB values atomically. An invalid-size or incomplete
PDU does nothing.

`0x701` and the six-colour `LedColour`/colour-code state are removed in phase
2 rather than retained as a second LED-output path. Existing non-LED direct
frames are unchanged.

### Public and virtual rendering state

`buttons.led_rgb` becomes the only public controller-requested button-pad LED
state: exactly 16 `[red, green, blue]` byte triples. It replaces
`buttons.led_colours` everywhere in controller models, generated live schema,
Socket.IO types, fixtures, tests, and the workbench. It is requested state, not
a physical-output acknowledgement.

The simulated pad independently reassembles and validates the actual CAN
transfer. Tests prove its private applied RGB state equals the coordinator
snapshot. The browser may render the public requested RGB state; it must not
add an observed/applied public LED truth merely to display the pad.

The existing 3D button, inset colour ring, border, and surface casts remain.
The frontend derives CSS variables from RGB at the rendering boundary only:

- zero RGB is off and contributes no LED-derived tint;
- normalize nonzero RGB by its largest channel to preserve hue;
- calculate perceptual visual intensity as `(largestChannel / 255)^(1 / 2.2)`;
- scale the existing ring, border, cast, and lower-shadow opacities from that
  value.

RGBA is not put on CAN and is not part of `led_rgb`.

## Implementation phases

| Phase | Document | Outcome |
|---:|---|---|
| 1 | [Transport foundation](phase-1-transport-foundation.md) | Generated IDs, pinned dependencies, Python/C++ ISO-TP adapters, and cross-endpoint opaque-payload tests. |
| 2 | [RGB virtual vertical slice](phase-2-rgb-virtual-button-pad.md) | Canonical RGB state, 48-byte PDU, simulator delivery, and virtual-pad rendering. |

## Deferred hardware follow-on

Only after the two phases are complete and NeoTrellis hardware facts are
recorded may a separate design add a renderer using Adafruit's
`Adafruit_Seesaw` library. That design must address I²C topology, logical to
physical mapping, gamma/current limits, safe output on lease loss, and bench
evidence. It is not implicit authorization to connect the device to the car.

## Implementation rules

- One phase per agent run. Complete a phase before starting its successor.
- Reuse the two selected ISO-TP libraries; do not implement a parallel custom
  segmenter or an abstraction over several transports.
- Keep adapters at the CAN boundary. Do not create a generic device framework,
  command bus, effect engine, receipt model, or browser transport provider.
- Prefer replacing the indexed LED path completely in phase 2 over keeping
  aliases, compatibility state, or dual publication.
- Tests must use real encoded ISO-TP CAN frames on the simulated bus. Never
  set simulated-pad RGB state directly to manufacture a successful scenario.
- Software/simulation success is not collision proof, bench validation, or
  physical output evidence.

Use [the phase prompt](phase-agent-prompt.md) for each implementation run and
update [the implementation log](implementation-log.md) in the same change.
