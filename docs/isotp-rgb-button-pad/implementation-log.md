# ISO-TP/RGB button-pad implementation log

[Overview](README.md) · [Phase prompt](phase-agent-prompt.md)

This is the append-only record for the two phases. Read it completely before
starting a phase, update the status row and append an entry in the same change,
and do not rewrite prior entries except to correct factual errors.

## Phase status

| Phase | Status | Completed by | Date | Verification |
|---|---|---|---|---|
| 1 | Completed | /root/phase1_transport | 2026-07-17 | `pytest`, Ruff, mypy, generator check, and Arduino Micro build passed. |
| 2 | Completed | /root/phase2_rgb_virtual | 2026-07-17 | Full coordinator suite, lint/types, generated checks, relevant frontend tests/typecheck, and Arduino Micro build passed. |

Allowed statuses are Not started, In progress, Completed, and Blocked. A phase
is not complete until every required check in its phase document passed. A
blocked entry must identify the concrete blocker and the repository state.

## Entries

### Entry template

```markdown
### Phase <number> — <title> — <YYYY-MM-DD>

- **Agent:** <identifier or "not available">
- **Final status:** <Completed or Blocked>

#### Summary

<Outcome and intentionally excluded work.>

#### Important files changed

- `<path>` — <reason>

#### Public contract or wire changes

<Exact change, or "None".>

#### Verification

| Command | Result |
|---|---|
| `<exact command>` | <result> |

#### Decisions, deviations, and limitations

- <Decision/deviation/limitation, or "None beyond the phase document".>

#### Follow-up work

- <Specific next phase or hardware-evidence item.>
```

### Phase 1 — Transport foundation — 2026-07-17

- **Agent:** /root/phase1_transport
- **Final status:** Completed

#### Summary

Added the bounded 256-byte ISO-TP button-pad link and generated `0x708`/`0x709`
constants. Python simulation endpoints use pinned `can-isotp`; the Arduino
Micro compiles a local `isotp-c` wrapper with static send/receive buffers.
Completed payloads are private and only serial-logged/discarded by firmware.
No RGB, UI, public-state, acknowledgement, or physical LED work was added.

#### Important files changed

- `protocol/custom.toml` and generated artifacts — transport IDs and limit.
- `coordinator/src/e87canbus/transport/isotp.py` — bounded Python CAN adapter.
- `coordinator/src/e87canbus/simulation/devices.py` — simulated pad transport endpoint.
- `embedded-libs/isotp_transport/` — reusable firmware wrapper and licence attribution.
- `devices/button-pad/src/main.cpp` — MCP2515 frame/time bridge only.

#### Public contract or wire changes

Added simulation/bench-only ISO-TP IDs `0x708` (coordinator to pad) and `0x709`
(pad to coordinator), with a maximum reassembled payload of 256 bytes. Existing
direct message encodings are unchanged.

#### Verification

| Command | Result |
|---|---|
| `uv run ruff check coordinator/src/e87canbus coordinator/tests/test_isotp_transport.py` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed (64 source files). |
| `uv run python scripts/generate_custom_protocol.py --check` | Passed. |
| `uv run pytest -q` | Passed (547 tests). |
| `cd devices/button-pad && pio run` | Passed; Arduino Micro firmware built. |
| `git diff --check` | Passed. |

#### Decisions, deviations, and limitations

- `can-isotp` owns ISO-TP framing/timers; focused tests advance its monotonic timer without sleeping.
- The build is not hardware, bus-collision, bench, or in-car validation. Arduino RAM use is 1713/2560 bytes (66.9%) after adding the two fixed 256-byte transport buffers.

#### Follow-up work

- Phase 2 may add the sole 48-byte RGB snapshot consumer and virtual rendering; physical NeoTrellis output remains deferred.

### Phase 2 — RGB virtual button pad — 2026-07-17

- **Agent:** /root/phase2_rgb_virtual
- **Final status:** Completed

#### Summary

Replaced the production indexed `0x701` LED path with the canonical 16×RGB
snapshot codec and ISO-TP sender/receiver path. The virtual pad now consumes
only complete 48-byte payloads and the workbench derives its existing key
layers from normalized RGB plus perceptual intensity. No effects, receipts,
Seesaw, physical output, or browser transport were added.

#### Important files changed

- `coordinator/src/e87canbus/protocol/can.py` — exact 48-byte RGB codec.
- `coordinator/src/e87canbus/output.py` — coordinator ISO-TP RGB sender and Flow Control intake.
- `coordinator/src/e87canbus/simulation/devices.py` — atomic simulated-pad RGB application.
- `frontend/src/components/simulator-workbench/components/neo-trellis-panel/components/neo-trellis-button/led-style.ts` — pure RGB visual transform.
- `protocol/custom.toml` and generated artifacts — removed the fixed `0x701` definition.
- `README.md`, `docs/simulation.md`, and `docs/wiring.md` — active documentation now describes the ISO-TP RGB path and deferred physical output.

#### Public contract or wire changes

`buttons.led_rgb` replaces `buttons.led_colours`; the only LED PDU is exactly
48 bytes of 16 ordered RGB triples sent through ISO-TP.

#### Verification

| Command | Result |
|---|---|
| `uv run ruff check coordinator/src/e87canbus coordinator/tests/test_rgb_snapshot.py` | Passed. |
| `uv run ruff check .` | Passed after splitting the generated Markdown-table line in `scripts/generate_custom_protocol.py`. |
| `uv run pytest -q coordinator/tests/test_isotp_transport.py coordinator/tests/test_rgb_snapshot.py` | Passed (6 tests). |
| `uv run mypy coordinator/src/e87canbus` | Passed. |
| `uv run python scripts/generate_custom_protocol.py --check` | Passed. |
| `uv run python scripts/generate_live_contract.py --check` | Passed. |
| `cd frontend && pnpm run typecheck` | Passed. |
| `cd frontend && pnpm exec vitest run src/components/simulator-workbench/live-availability.test.tsx src/live/live-render.test.tsx` | Passed (4 tests). |
| `cd devices/button-pad && pio run` | Passed. |
| `uv run pytest -q` | Passed (544 tests) after migrating legacy indexed-colour tests to RGB expectations. |
| Active-document search for `0x701`/`led_colours` | Passed; no active root/protocol/simulation/device documentation retains the removed LED path. |
| `git diff --check` | Passed. |

#### Decisions, deviations, and limitations

- The coordinator endpoint receives ISO-TP Flow Control frames through the existing runtime receive path; no application acknowledgement was added.
- Physical NeoTrellis rendering remains deferred.
- The simulated runtime test proves a coordinator ISO-TP transfer reaches the pad's private applied `led_rgb` only after the transport completes.
- A final documentation correction keeps the browser's requested `buttons.led_rgb` distinct from the simulated pad's private applied state.

#### Follow-up work

- Physical NeoTrellis output remains a separately designed, hardware-evidence-gated follow-on.
