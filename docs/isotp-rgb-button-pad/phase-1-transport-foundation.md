# Phase 1 — Transport foundation

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Phase prompt](phase-agent-prompt.md)

**Status:** Not started.

## Outcome

Implement the bounded ISO-TP wire transport on the provisional button-pad
link. At the end of this phase, the coordinator and the Python simulated pad
can exchange arbitrary opaque payloads of at most 256 bytes over real
simulated CAN frames. The Arduino Micro button-pad project compiles the same
wire transport through the repository-owned C++ wrapper.

No application consumes a completed payload yet.

## Implementation shape

Keep this phase to three real boundaries:

1. **Protocol constants.** Add one compact transport-link entry to the source
   protocol definition. The generator/configuration type exposes its two IDs
   and one maximum size; no Python or firmware caller contains literal
   transport IDs.
2. **Python endpoint adapter.** Add one small coordinator transport module,
   such as `e87canbus.transport.isotp`, around `can-isotp`. It converts only
   between the package's CAN-message value and this repository's `CanFrame`,
   owns a link's RX/TX IDs and 256-byte limit, and exposes `on_frame`, `poll`,
   and `send`/completed-payload operations. It does not know about controller
   state, effects, live events, or the virtual UI.
3. **Firmware endpoint adapter.** Add one local PlatformIO C++ library around
   `isotp-c`. It owns the static send/receive buffers and callback bridge; the
   button-pad `main.cpp` remains the MCP2515 adapter and calls the library from
   its normal receive/poll loop. Do not copy ISO-TP logic into `main.cpp`.

The simulated coordinator endpoint and simulated pad endpoint each use their
own Python adapter instance on their existing in-memory CAN endpoints. Feed a
received matching CAN frame to `on_frame`, call `poll` during ordinary runtime
progress, and let the package emit frames through the existing bus. A fake
monotonic clock must drive both endpoints in tests. No extra thread, async
task, queue, Socket.IO event, or transport status publication is needed.

On firmware, provide `isotp-c` only the smallest bridge it requires: send one
classic CAN frame through the existing MCP2515 instance and return `micros()`.
The project wrapper, not the upstream library default, fixes the 256-byte
capacity. It should expose a completed payload only after `isotp-c` has
finished reassembly; phase 1 discards or serial-logs that payload.

## Required changes

1. Extend the source custom protocol definition with the two ISO-TP link IDs
   and the one 256-byte maximum. Generate the Python/configuration, firmware,
   and Markdown constants from it. Keep ISO-TP frame encoding out of the
   fixed-message generator.
2. Add the pinned Python `can-isotp==2.0.7` dependency and a narrow Python CAN
   adapter that works with the repository's `CanFrame`/in-memory topology.
   Use it for both the coordinator-side link and `SimulatedNeoTrellisNode`.
3. Add the pinned `isotp-c` commit as a PlatformIO dependency and licence
   attribution. Add one small project C++ wrapper library with fixed 256-byte
   capacity, a nonblocking `poll`/incoming-frame entry point, a `busy` send
   result, and a completed-payload callback or retrieval API.
4. Feed the wrapper only transport IDs from the existing Arduino CAN receive
   loop and call its poll method from the existing nonblocking loop. Completed
   payloads may be logged or discarded; they must not change LED state.
5. Keep each endpoint's transport state private. Do not publish it through the
   live API, browser, health model, or device registry.

Do not add a production command merely to exercise the transport. Focused
tests may invoke the endpoint's opaque-payload API directly.

## Required tests

- Generated-ID/configuration validation and exact ISO-TP ID documentation.
- Python controller ↔ simulated-pad interoperability for one 48-byte opaque
  payload in each direction, using the in-memory CAN topology.
- Single-frame transport delivery.
- Receiver flow-control/pacing behavior suitable for the simulated bus.
- Oversize declaration, bad consecutive-frame sequence, and timeout discard
  partial data without exposing it.
- A second same-direction send while active returns `busy` and does not
  interleave frames.
- Existing direct button, registration, heartbeat, and simulator behavior
  regressions.
- A clean Arduino Micro PlatformIO build. No USB hardware or vehicle test is
  required for phase completion.

Use fake monotonic time in tests; never sleep. Tests may assert ISO-TP Flow
Control frames but must not introduce application acknowledgements.

## Acceptance criteria

- Every phase-1 transport payload is at most 256 bytes at both endpoints.
- The simulated bus transports bytes only through ISO-TP frames, not a direct
  shortcut.
- No application state, public schema, LED state, or UI changes.
- Existing direct custom message encodings remain byte-for-byte unchanged.
- Required focused tests, full coordinator tests, generated checks, lint/type
  checks, and Arduino build pass.

## Explicitly deferred

RGB payload definition/handling, deleting the indexed LED protocol, frontend
changes, `Adafruit_Seesaw`, effects, output acknowledgements, retries, and
physical validation are phase 2 or later work.
