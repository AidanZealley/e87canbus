# Phase 2 — RGB virtual button pad

[Overview](README.md) · [Implementation log](implementation-log.md) ·
[Phase prompt](phase-agent-prompt.md)

**Status:** Not started. Requires phase 1 completed.

## Outcome

Replace the indexed 16-colour LED path with one atomic 16×RGB snapshot PDU.
The coordinator emits the 48-byte payload through the completed ISO-TP
transport, the Python simulated pad reassembles it, and the browser workbench
renders canonical RGB with its existing layered 3D key treatment.

## Implementation shape

Keep the existing controller/output ownership where it is clear. Retain the
logical `ButtonLedState` and `SetButtonLeds` concepts if their existing
ownership and effect-execution path remain suitable; change their value from
indexed `LedColour` codes to an exact immutable 16×RGB value. Remove
`LedColour` and colour-code packing rather than creating parallel RGB names or
conversion adapters.

Place the 48-byte encode/decode next to the existing project CAN payload
codecs. It has one responsibility: validate/extract 16 triples in button order.
It must not know about ISO-TP state. The output executor passes its encoded
bytes to the phase-1 endpoint; the simulator supplies only completed payloads
to the matching decoder. This keeps application payload validation distinct
from transport reassembly without adding a general PDU framework.

The public live model contains a fixed-length RGB tuple/list, and generated
schema/types are derived from that one model. The frontend consumes that normal
JSON state directly. Add one pure visual helper beside the workbench button
component that turns an RGB triple into CSS custom-property values; pass those
values into the current component. Do not add a provider, animation loop,
canvas, new store, or React transport code for a static snapshot.

## Required changes

1. Replace indexed `LedColour`, colour-code codecs, the generated `0x701`
   message, and all callers with one exact-length RGB snapshot value/codec.
   Retain existing `ButtonLedState`/`SetButtonLeds` ownership only by changing
   their contained LED value to RGB; do not leave aliases, fallback output, or
   a second LED transport path.
2. Change controller-derived LED intent to exact RGB triples and send it only
   through the phase-1 coordinator-to-pad ISO-TP link. A changed state emits
   one complete 48-byte snapshot, subject to the existing explicit TX policy.
3. Make `SimulatedNeoTrellisNode` accept only completed 48-byte RGB payloads
   while operational with a fresh controller lease. Validate size and atomically
   replace its private 16-key RGB state. Invalid payloads must preserve the
   prior state.
4. Replace the live contract, API types, Zustand state, fixtures, and UI uses
   of `buttons.led_colours` with `buttons.led_rgb`, exactly 16 RGB triples.
   Regenerate the schema through its source model and generator.
5. Replace `rgbForColourCode` in the workbench with the RGB values directly.
   Preserve the existing button structure and interaction behavior. Add only a
   pure RGB-to-CSS-variable helper plus the smallest style-variable changes
   needed to scale the current ring/border/cast/shadow layers as specified in
   the overview.
6. Update protocol, simulation, device, and root documentation to say that
   physical NeoTrellis rendering remains deferred. Do not add Seesaw in this
   phase.

## Required tests

- Exact 48-byte RGB vector and malformed-length validation.
- Coordinator emits the expected ISO-TP PDU bytes and no `0x701` LED frame.
- Simulated pad receives the PDU through phase-1 transport and atomically
  applies all 16 RGB values; malformed/incomplete transfers preserve its prior
  private state.
- Existing application decisions map to the expected RGB triples.
- Generated live-schema and TypeScript contract checks confirm `led_rgb` has
  exactly 16 RGB triples and no `led_colours` field remains.
- Frontend component tests cover off, full-brightness, and dim nonzero RGB;
  assert derived hue and opacity variables rather than fragile shadow strings.
- Existing simulator control behavior, direct button events, and device lease
  gates regress correctly.
- Full coordinator/frontend checks and clean Arduino Micro build pass.

## Acceptance criteria

- One canonical `buttons.led_rgb` state exists; no indexed LED state or
  `0x701` LED output remains.
- A full virtual RGB update uses actual ISO-TP frames and changes the virtual
  pad only after the simulated endpoint has received the whole snapshot.
- The browser receives normal live JSON, not ISO-TP frames, and adds no
  observed/applied LED public state.
- No effects, acknowledgements, Seesaw, or hardware claims are introduced.
