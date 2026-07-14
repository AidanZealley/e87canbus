# Implementation Log — Hardening Pass 03

Append one entry per completed phase. Do not edit earlier entries after a later phase begins; record
corrections in the current entry.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Atomic LED snapshot cutover | done | 2026-07-13 |
| 2 — Policy proof and legacy cleanup | planned | — |
| 3 — Verified physical NeoTrellis rendering | blocked on verified hardware evidence | — |

## Entry template

```markdown
## Phase N — <title> (<date>)

**Result:** done | done with deviations | blocked

**What changed:**

- Factual bullets naming affected boundaries.

**Deviations from the phase doc:** None, or each deviation and its reason.

**Safety invariants verified:** Name the relevant invariants and tests.

**Complexity delta:** Name deleted indexed paths and compatibility code, new invariant-enforcing
values, and any deliberately retained complexity.

**Discovered along the way:** New constraints or follow-up work. "Nothing" is valid.

**Checks:** Backend / frontend / generator / firmware results as applicable.
```

## Phase 1 — Atomic LED snapshot cutover (2026-07-13)

**Result:** done

**What changed:**

- Added the frozen, exact-length `ButtonLedState` domain value and replaced the indexed effect with
  one `SetButtonLeds` effect. Startup emits one complete LED effect, and button transitions emit one
  only when the committed state's complete LED projection changes.
- Replaced the provisional `0x701` DLC-2 protocol with one DLC-8 nibble-packed snapshot in the TOML
  source, generated Python constants, firmware header, and generated Markdown. The direct Python
  codec validates all 16 colour codes before returning a payload.
- Kept the executor and network-wide `SafeCanTransmitter` as the sole coordinator write path. The
  isolated bench app now owns one immutable 16-colour state and sends snapshots through the shared
  effect/router/executor path.
- Changed the simulated button pad to decode the production codec and replace one complete tuple
  after validation. API/WebSocket snapshots and frontend state now expose and replace all 16
  positions, and the trace view uses one shared DLC-8 nibble decoder.
- Changed firmware to decode into a temporary 16-byte array, reject wrong DLC or any invalid nibble,
  then copy the complete stored state and call one reporting/rendering boundary. No NeoTrellis
  topology, mapping, brightness, or electrical assumptions were added.
- Updated current-facing bench, deployment, simulation, protocol, and project-context documentation.

**Deviations from the phase doc:** None. The supplemental `led_update` WebSocket path named by the
phase no longer existed because hardening-02 had already removed parallel incremental publication;
the existing holistic snapshot publication was changed directly to a complete 16-value LED array,
without adding a second event path.

**Safety invariants verified:** One application LED effect encodes to one `0x701` DLC-8 frame;
explicit-TX startup sends exactly one such frame; default live composition still sends none;
simulation retains its prior state after wrong-length and invalid-final-nibble frames; valid
snapshots replace all 16 entries; browser button actions still traverse the external device,
production button encoder/frame/router, transition/commit, effect/executor/policy, production LED
codec, and simulated device-state path. The provisional IDs remain simulation/bench-only and the TX
window remains network-wide and independent of LED count.

**Complexity delta:** Deleted `SetButtonLed`, `LedUpdatePayload`, the DLC-2 encoder/decoder, generated
index/colour byte constants, mutable sparse simulated LED dictionaries, two-frame startup output,
and all current-facing indexed-update descriptions. Added only two invariant-enforcing frozen
values (`ButtonLedState` and domain-neutral `LedSnapshotPayload`) plus direct codecs. The audit also
deleted an initially considered indexed snapshot-replacement helper, leaving no retained indexed
mutation API, compatibility codec, registry, callback chain, retry queue, or LED-specific policy.
The firmware's temporary decode array is deliberately retained because it enforces all-or-nothing
validation and isolates stored state from malformed input.

**Discovered along the way:** The frontend test command enumerated test files explicitly, so the new
trace-codec test was added to that command. Existing firmware tooling has no host-native codec test
target without introducing a new framework; agreement is therefore covered by generated constants,
Python golden vectors (including invalid final nibble), simulator atomicity tests, frontend vectors,
generator drift checking, and the successful PlatformIO build, as permitted by the phase.

**Checks:** `uv run pytest -q` — 213 passed (one existing FastAPI/Starlette deprecation warning);
`uv run mypy` — success, 30 source files; `uv run ruff check coordinator` — passed;
`cd frontend && pnpm typecheck && pnpm lint && pnpm test` — passed, 10 tests;
`uv run python scripts/generate_custom_protocol.py --check` — passed; and
`cd devices/button-pad && pio run` — passed for the Arduino Micro target (RAM 21.5%, flash 25.6%).
