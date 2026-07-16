# Device registry implementation log

[Overview](README.md) · [Phase agent prompt](phase-agent-prompt.md)

This is the shared append-oriented record for the device-registry phases. Read
the complete log before starting a phase. After completing or blocking a
phase, update its status row and append an entry using the template below in
the same change as the implementation.

Do not rewrite earlier entries except to correct a factual error. Later agents
must be able to see the state, decisions, deviations, and verification handed
to them.

## Phase status

| Phase | Status | Completed by | Date | Verification |
|---|---|---|---|---|
| 1 | Completed | Codex lead after James/Gibbs workers | 2026-07-16 | Generated check; focused protocol/config/architecture tests (79 passed); full coordinator suite (516 passed) |
| 2 | Not started | — | — | — |
| 3 | Not started | — | — | — |
| 4 | Not started | — | — | — |
| 5 | Not started | — | — | — |

Allowed statuses are:

- Not started
- In progress
- Completed
- Blocked

A phase must not be recorded as completed while any required acceptance test
is failing or was not run. A blocked entry must identify the concrete blocker,
the checks already attempted, and the current repository state.

## Entries

### Phase 1 — Specification and protocol — 2026-07-16

- **Agent:** James (initial implementation), Gibbs (compatibility repair), and Codex lead audit
- **Final status:** Completed

#### Summary

Established the version 1 custom-device vocabulary and generated CAN protocol foundation. The
catalogue now contains one enabled, single-instance identity for `button_pad` and
`servotronic_controller`; `DeviceSource` is limited to physical, emulated, and disabled; and the
seven public registry lifecycle values are defined for later kernel work. The generator now owns
all eight project messages and produces synchronized Python, Arduino, and Markdown artifacts.
Strict HELLO, WELCOME_ACK, and HEARTBEAT payload codecs cover both role-specific ID families and
the exact overview vectors, including malformed-frame boundaries. The optional device directory
and active terminology were renamed to Servotronic, and stale observer-source callers were removed.

#### Important files changed

- `protocol/custom.toml` — sole source for protocol version, IDs, layouts, and values.
- `scripts/generate_custom_protocol.py` — generic message parsing and Python/header/Markdown generation.
- `coordinator/src/e87canbus/protocol/generated.py` — generated Python protocol constants.
- `devices/button-pad/include/can_ids.h` — generated firmware constants.
- `coordinator/src/e87canbus/protocol/can.py` — strict registry payload values and codecs.
- `coordinator/src/e87canbus/device.py` — static role, source, lifecycle, identity, and catalogue types.
- `coordinator/src/e87canbus/config.py` — generated custom CAN IDs with standard-ID and uniqueness validation.
- `devices/servotronic-controller/README.md` and repository documentation — consistent optional-device naming and deferred hardware boundaries.
- `coordinator/src/e87canbus/api/models/live.py` — keeps the current button-pad-only health projection type-safe until the phase 3 registry projection.
- `coordinator/tests/test_can_protocol.py`, `coordinator/tests/test_config.py`, and `coordinator/tests/test_generated_protocol.py` — vector, malformed-frame, catalogue, and artifact checks.

#### Public contract or schema changes

- Added generated `CUSTOM_DEVICE_PROTOCOL_VERSION = 1` and role-specific IDs `0x702`–`0x707`.
- Added typed `DeviceHelloPayload`, `DeviceWelcomeAckPayload`, and `DeviceHeartbeatPayload` codecs with DLC, field-width, reserved-byte, response-code, and standard-ID validation.
- Added `DeviceRole.SERVOTRONIC_CONTROLLER`, the reduced `DeviceSource` vocabulary, `DeviceLifecycleStatus`, immutable device identity/catalogue types, and the default two-role catalogue.
- Preserved the existing `0x700` button-event and `0x701` atomic LED snapshot payloads.

#### Verification

| Command | Result |
|---|---|
| `uv run python scripts/generate_custom_protocol.py --check` | Passed; generated artifacts current. |
| `uv run pytest coordinator/tests/test_generated_protocol.py coordinator/tests/test_can_protocol.py coordinator/tests/test_config.py coordinator/tests/test_architecture.py` | Passed; 79 tests. |
| `uv run pytest coordinator/tests` | Passed; 516 tests, 1 existing Starlette deprecation warning. |
| `uv run ruff check .` | Passed. |
| `uv run mypy coordinator/src/e87canbus` | Passed; 61 source files. |
| `git diff --check` | Passed. |

#### Decisions and assumptions

- One generic codec implementation is parameterized by the role-specific arbitration ID because both registry ID families have identical payload layouts.
- LED packing remains the only targeted generator metadata special case; all message IDs, fields, and values come from `protocol/custom.toml`.
- The pre-registry `DeviceProjection` remains temporarily for its current live/simulation consumers and is explicitly scheduled for removal in phase 3; no new public LED truth was added.
- The current live health adapter still publishes only its existing button-pad entry; its type boundary is kept explicit until phase 3 projects the complete registry role map.

#### Deviations from the phase document

- None.

#### Known limitations

- Runtime registry transitions, feature gating, live-contract migration, simulation peers, firmware behavior, live K-CAN acknowledgement authorization, collision validation, bench evidence, and physical readiness remain deferred to later phases or documented evidence gates.

#### Follow-up work

- Phase 2 must make the kernel the sole registry owner, consume these generated codecs/catalogue types, and implement lifecycle/timing and server-side gating without redeclaring protocol layouts.
- Remove the temporary `DeviceProjection` and migrate the live contract in phase 3.

---

## Entry template

Copy this section to the end of **Entries** and replace every placeholder.

```markdown
### Phase <number> — <title> — <YYYY-MM-DD>

- **Agent:** <identifier, name, or "not available">
- **Final status:** <Completed or Blocked>

#### Summary

<What was implemented and what user-visible/runtime result now exists.>

#### Important files changed

- `<path>` — <reason>

#### Public contract or schema changes

<List exact API, event, type, wire, configuration, or generated-artifact
changes. Write "None" when there were none.>

#### Verification

| Command | Result |
|---|---|
| `<exact command>` | <passed/failed/not run and relevant counts or error> |

#### Decisions and assumptions

- <Any implementation-level decision not already fixed by the phase document.>

#### Deviations from the phase document

- <Deviation and reason, or "None".>

#### Known limitations

- <Limitation, or "None beyond the documented deferred scope".>

#### Follow-up work

- <Specific work for later phases or physical validation.>
```
