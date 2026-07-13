# Phase 1 — Atomic LED Snapshot Cutover

## Goal

Replace every repository-owned indexed LED mutation boundary with one complete 16-colour snapshot,
without retaining a legacy production path.

## Domain and transition

- Add a frozen value representing exactly 16 `LedColour` entries. Construction with any other
  length fails.
- Replace `SetButtonLed` with `SetButtonLeds` carrying that value.
- Derive all positions from committed application state: button 0 reflects steering mode, button 3
  reflects maximum assistance, and every currently unassigned position is `OFF`.
- Startup emits one snapshot. A transition emits one snapshot only when its LED projection changes.
  Assistance-level changes that do not alter any LED emit none.
- Pure transition tests compare the complete literal snapshot and prove equal inputs return equal
  results.

The isolated bench ping-pong application owns its own small immutable 16-colour state because it is
not the coordinator application. Each accepted button event replaces one position in that value and
emits the complete snapshot through the shared executor. Do not reintroduce direct CAN writes.

## Protocol source and codec

Extend the machine-readable protocol source established by hardening-02 phase 7 with:

- LED count 16;
- DLC 8;
- even-index/low-nibble and odd-index/high-nibble ordering; and
- the valid nibble range derived from the existing colour codes.

Regenerate Python, firmware header, and Markdown artifacts. Replace `LedUpdatePayload`,
`encode_led_update`, and `decode_led_update` with snapshot names and behavior. The decoder validates
all eight bytes before constructing a domain-neutral wire payload. Delete the DLC-2 codec and its
index/colour byte constants in this phase.

Golden vectors must include:

- all LEDs off → `00 00 00 00 00 00 00 00`;
- LED 0 blue and LED 3 white → `03 50 00 00 00 00 00 00`;
- distinct neighbouring nibbles proving even/low and odd/high ordering;
- wrong DLC; and
- an invalid nibble in the final byte proving no prefix is returned.

## Application effect and network path

The router maps `SetButtonLeds` to exactly one routed `0x701` frame. The existing `EffectExecutor`
and `SafeCanTransmitter` remain the only coordinator write path; the frame consumes one unit of the
network-wide window. Do not add an LED-specific limiter or per-ID allowance.

## Simulator and API

- The simulated button pad decodes the production snapshot and replaces a complete 16-entry state
  only after full validation.
- Snapshots and API responses expose all 16 positions, including `OFF` values.
- Replace supplemental `led_update` events with `led_snapshot` carrying all colour codes. WebSocket
  consumers replace rather than merge LED state.
- Malformed frames are logged once and leave the prior simulated LED state unchanged.
- Browser actions still emit real `0x700` frames through the external simulated node.

## Frontend

- Replace indexed `LedUpdateEvent` with a complete snapshot event.
- Replace merge logic with complete state replacement.
- Update CAN trace formatting to decode the DLC-8 nibble layout and display all 16 values compactly.
- Keep the existing 16-button presentation; no animation or brightness feature belongs here.

## Firmware

- Replace indexed DLC-2 handling with full DLC-8 validation.
- Decode into a temporary 16-byte colour array, validate every colour, then replace the stored
  snapshot and call one rendering boundary. Never mutate the stored array during validation.
- For the current milestone hardware, the rendering boundary may report/store the validated values;
  it must not invent an unverified NeoTrellis address or electrical configuration.
- Add host-testable codec vectors if the existing firmware tooling supports them without a new test
  framework; otherwise cover wire agreement through generated artifacts, Python golden vectors, and
  a successful PlatformIO build, and record the limitation.

## Acceptance criteria

- One application LED effect encodes to one DLC-8 frame containing all 16 colours.
- Startup transmits exactly one `0x701` frame under an explicit TX grant.
- No DLC-2 LED codec, indexed LED effect, or direct coordinator/bench LED write remains.
- Firmware and simulation reject wrong-length or invalid-colour frames without changing state.
- Simulator, API, WebSocket, frontend, and trace views agree on all 16 positions.
- Generated protocol `--check`, backend, frontend, and firmware checks pass.
