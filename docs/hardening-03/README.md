# Hardening Pass 03 — Atomic Button-Pad LED Snapshots

This pass replaces indexed LED mutation messages with one complete, idempotent button-pad LED
snapshot. It is intentionally separate from hardening pass 02: pass 02 establishes the event kernel
and holistic network output boundary, while this pass changes the repository-owned button-pad
protocol, firmware, simulator, API, and frontend together.

Do not begin this pass until hardening-02 phase 7 has established the generated protocol source of
truth. This pass depends on hardening-02 phases 1–7, but not on the externally blocked steering
failsafe in phase 8.

## Outcome

```text
application state
      │
      ▼
derive complete 16-LED state
      │
      ▼
SetButtonLeds(snapshot)                 one immutable domain effect
      │
      ▼
encode 0x701 DLC-8                     one complete wire snapshot
      │
      ▼
network-wide TX safety window          independent of LED count
      │
      ▼
button-pad validates all 16 colours
      │
      ▼
replace complete device LED state      no partial application
```

## Binding design

### Domain state and effect

- The button pad has exactly 16 LED positions, numbered 0 through 15.
- Add a frozen LED-state value that rejects any tuple not containing exactly 16 `LedColour` values.
- Application state remains authoritative. LED state is a derived projection of application state,
  not a second independently mutable copy inside the coordinator.
- Replace `SetButtonLed(button_index, colour)` with `SetButtonLeds(colours)` carrying the complete
  validated state.
- Startup and every transition whose LED projection changes emit at most one LED effect.
- Unassigned positions are explicitly `OFF`; missing dictionary keys are not an LED state.

### Wire format

Keep the provisional coordinator-to-button-pad arbitration ID `0x701`, but replace its legacy DLC-2
indexed payload with one DLC-8 snapshot:

```text
byte 0: low nibble = LED 0,  high nibble = LED 1
byte 1: low nibble = LED 2,  high nibble = LED 3
...
byte 7: low nibble = LED 14, high nibble = LED 15
```

Colour codes remain `0x0` through `0x5`. Nibbles `0x6` through `0xf` are invalid. A decoder validates
the arbitration ID, DLC, and every nibble before returning a snapshot. One invalid nibble rejects the
entire frame; neither firmware nor simulation applies a prefix.

The DLC-2 format is deleted in the cutover phase. Do not retain dual decoding, a version switch, or
an indefinite compatibility encoder. The protocol is provisional and all repository-owned
participants move together.

### Safety policy

- LED count and synchronization transaction size do not appear in TX-policy configuration.
- Every complete LED snapshot consumes one unit of the existing per-network sliding-window budget.
- There is no per-ID window and no indexed-frame burst allowance.
- Excess output is logged and dropped, never queued. The next accepted full snapshot converges the
  device without replaying stale intermediate LED mutations.
- Default live composition remains RX-only. This pass does not validate `0x701` for in-car use or
  grant live K-CAN transmission.
- Future actuator traffic retains its separate evidence-derived refresh policy.

### Publication and simulation

- Simulated external button-pad nodes decode the production DLC-8 frame and replace all 16 colours
  together.
- Browser commands continue to operate the simulated external node; no LED state injection API is
  added.
- API/WebSocket LED notifications carry a complete snapshot. The frontend replaces its LED state
  instead of merging one indexed mutation.
- CAN trace formatting decodes all 16 nibbles through a shared frontend helper rather than manually
  slicing one index/colour pair.

### Firmware boundary

- Generated protocol artifacts own the DLC, LED count, nibble order, and colour codes.
- The current milestone firmware must validate and store a complete 16-colour snapshot atomically
  before reporting or rendering it.
- Physical NeoTrellis rendering is phase 3 and remains blocked until the actual board topology,
  library, address mapping, brightness, and current budget are verified. Phase 1 must not invent
  those hardware facts.

## Binding invariants

1. One application decision produces zero or one complete LED effect, never a sequence of indexed
   LED mutations.
2. A complete LED effect produces exactly one CAN frame.
3. Legal LED state always contains exactly 16 known colours; partial state is not representable.
4. Firmware and simulation reject malformed snapshots without changing any LED.
5. Accepted snapshots replace all 16 LEDs atomically and are idempotent.
6. Simulation uses the production effect, encoder, network policy, decoder, and device-state path.
7. Frequency policy is network-wide and independent of LED count or current startup behavior.
8. Protocol definition, generated Python, firmware header, and Markdown cannot drift silently.
9. Default live composition has no transmitter capability.
10. The provisional IDs gain no new live deployment authority from this pass.

## Phases

| # | Document | Result | Depends on |
|---|---|---|---|
| 1 | [Atomic LED snapshot cutover](phase-1-atomic-snapshot.md) | Domain, protocol, firmware, simulator, API, and frontend use one complete snapshot | hardening-02 phases 1–7 |
| 2 | [Policy proof and legacy cleanup](phase-2-policy-and-cleanup.md) | Network-wide limits are proven and every indexed LED path/description is gone | 1 |
| 3 | [Verified physical NeoTrellis rendering](phase-3-verified-rendering.md) | Validated snapshots drive real pixels within verified electrical limits | 2 plus hardware evidence |

## Migration discipline

- Implement one phase at a time and append its result to `IMPLEMENTATION_LOG.md`.
- Phase 1 is a coordinated cutover. It may be broad, but it must not leave legacy DLC-2 and DLC-8
  production paths beside each other.
- Do not change arbitration IDs merely to avoid coordinating the cutover. `0x701` remains provisional
  and collision-gated.
- Prefer one immutable value and direct codecs over indexed update managers, diff engines, registries,
  or retry queues.
- Do not add animation, brightness control, physical button scanning, or steering behavior to this
  pass.
- Finish each phase with the simplification audit in `PROMPT.md`.

## Checks

Every phase must run:

```bash
uv run pytest -q
uv run mypy
uv run ruff check coordinator
cd frontend && pnpm typecheck && pnpm lint && pnpm test
```

Phases changing generated protocol artifacts must run the hardening-02 phase-7 generator in
`--check` mode. Phases changing button-pad firmware must also run:

```bash
cd devices/button-pad
pio run
```
