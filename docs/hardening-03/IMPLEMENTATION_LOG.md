# Implementation Log — Hardening Pass 03

Append one entry per completed phase. Do not edit earlier entries after a later phase begins; record
corrections in the current entry.

## Status

| Phase | Status | Completed |
|---|---|---|
| 1 — Atomic LED snapshot cutover | done | 2026-07-13 |
| 2 — Policy proof and legacy cleanup | done | 2026-07-14 |
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

## Phase 2 — Policy proof and legacy cleanup (2026-07-14)

**Result:** done with deviations

**What changed:**

- Added deterministic policy proofs that a complete 16-position LED effect consumes one network
  window entry, alternating `0x701` payloads share that window, and different arbitration IDs draw
  from the same budget. The refill test proves a dropped frame is absent rather than queued.
- Replaced the broad simulator budget-count test with an end-to-end proof: startup consumes the
  shared budget, a later LED decision is dropped without changing the simulated device, no frame is
  replayed at refill, and the next accepted production snapshot replaces all 16 colours and
  converges the device. A simulator session reset proves its new startup uses the same full effect,
  encoder, frame, decoder, device-state, executor, and policy path.
- Added one shared frontend exact-length/known-colour validator at the snapshot replacement
  boundary. Valid publications are copied and replace the complete LED array; short or
  invalid-final-value publications preserve the prior array atomically. The trace decoder reuses
  the same validation and LED-count constant, and the renderer no longer has a per-position
  malformed-array fallback.
- Reconciled the root, coordinator, protocol, bench, simulation, deployment, device, and wiring
  guides. They now state the DLC-8 complete-snapshot behavior, provisional collision gate,
  all-or-nothing replacement, holistic budget, and phase-3 physical-rendering gate. The default
  ceiling is documented as at most 20 coordinator frames in any rolling second per network,
  conservatively 2,700 bit/s (2.7% of 100 kbit/s or 0.54% of 500 kbit/s before errors and
  retransmissions), independent of LED count and human timing.

**Deviations from the phase doc:** There is no physical button-pad connection or reconnection signal
in the current provisional protocol, so no reconnect event or speculative synchronization manager
was added. The existing synchronization boundaries are kernel startup and simulator session
rebuild; both are covered by the network-policy proof. Browser WebSocket connections continue to
receive the current complete snapshot and do not create CAN output.

**Safety invariants verified:** One complete LED effect encodes to one DLC-8 frame and consumes one
shared network entry; all IDs share the network window; dropped output is neither queued nor
replayed; the next accepted snapshot replaces the complete simulated device state. Malformed CAN
and frontend snapshots leave every prior LED unchanged. The end-to-end simulator proof retains
input → decode → transition → commit → effect → policy ordering and production codecs/device state.
The default live composition remains unable to transmit, and `0x700`/`0x701` remain provisional,
bench/simulation-only, and collision-gated.

**Complexity delta:** No production Python or firmware path was added. The audit retained one frozen
domain LED state, one effect, one encoder, one decoder, and one complete publication field. It
removed the frontend renderer's indexed malformed-state fallback and duplicate trace LED-count and
colour-limit validation, replacing them with one exact-length/known-colour predicate shared by
publication and trace decoding. Repository-wide current-facing searches found no legacy
`LedUpdatePayload`, `SetButtonLed`, `led_update`, DLC-2 LED codec, indexed LED publication,
compatibility adapter, per-ID burst field, sparse LED dictionary, or stale current guide. The
frontend predicate is deliberately retained because it enforces atomic validation at an untrusted
JSON boundary.

**Discovered along the way:** The existing 20-frame default can be justified as a conservative
coordinator flood allocation without reference to startup behavior or LED count. Node's direct
TypeScript test runner requires an explicit `.ts` extension for the newly shared frontend import;
typecheck and lint accept that project convention. Physical NeoTrellis evidence remains absent, so
no topology, mapping, brightness, or current decision was introduced.

**Checks:** `uv run pytest -q` — 215 passed (one existing FastAPI/Starlette deprecation warning);
`uv run mypy` — success, 30 source files; `uv run ruff check coordinator` — passed;
`cd frontend && pnpm typecheck && pnpm lint && pnpm test` — passed, 11 tests;
`uv run python scripts/generate_custom_protocol.py --check` — passed; and
`cd devices/button-pad && pio run` — passed for the unchanged Arduino Micro target (RAM 21.5%,
flash 25.6%).
