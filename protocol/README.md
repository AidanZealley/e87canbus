# Protocol

Cross-device CAN protocol documentation and vehicle DBC material live here. Firmware and
coordinator implementations must agree with these definitions.

`custom.toml` is the source of truth for the provisional project messages. Run
`uv run python scripts/generate_custom_protocol.py` from the repository root to update the Python
constants, button-pad header, and generated section of `custom_ids.md`; use `--check` in verification.

Incoming definitions are scoped by logical network as well as arbitration ID. The current custom
`0x700`–`0x707` messages are provisional K-CAN bench/simulation definitions and need collision
validation before vehicle use.

Registry `HELLO`, `WELCOME_ACK`, and `HEARTBEAT` frames all use DLC 8 and unsigned little-endian
multi-byte fields. `HELLO` carries protocol version, stable device ID, device session ID, and
sequence, with bytes 6–7 reserved and required to be zero. `WELCOME_ACK` packs the controller
protocol version into the high nibble and response code into the low nibble; response `0` is
accepted and response `1` is unsupported protocol. It echoes the device ID, device session,
controller session, and device sequence. `HEARTBEAT` carries the stable device ID, device and
controller sessions, sequence, and an opaque status code where zero is healthy. Button-pad frames
use `0x702`–`0x704`; Servotronic-controller frames use the same layouts on `0x705`–`0x707`.

The conformance vectors for stable device ID `1`, device session `0x1234`, controller session
`0xABCD`, and button-pad IDs are:

```text
HELLO seq 0x56
  ID 0x702  data 01 01 00 34 12 56 00 00

accepted WELCOME_ACK
  ID 0x703  data 10 01 00 34 12 CD AB 56

healthy HEARTBEAT seq 0x57
  ID 0x704  data 01 00 34 12 CD AB 57 00
```

The Servotronic-controller vectors use IDs `0x705`–`0x707` with identical payloads. Unknown
devices, malformed DLC, nonzero reserved bytes, invalid fields, and extended-ID frames are not
registry payloads. Registry routing is K-CAN-only; the same arbitration IDs on PT-CAN or F-CAN are
not registry traffic.

Button-pad program v2 is an ordered sequence of 16-byte ISO-TP commands on `0x708`/`0x709`. The
first command opens a whole-pad replacement, every button is assigned exactly once across the
command masks, and bit 7 of the final opcode atomically commits the scene. Each command contains a 16-bit target mask and one resolved
track: solid, blink, or breathe; RGB, two kind-specific parameters, `repeat`, and final RGB. A repeat
of zero runs forever and a positive repeat count finishes on final RGB. The controller resolves the
base scene before encoding, so the AVR stores exactly one fixed-size base track per button. A
single-frame command on `0x701` starts finite press feedback — one opcode carrying a button index, a
pulse count of one or two, and an RGB triple — without replacing that base scene. Steady appearance,
animated or not, belongs to the program. Commands are paced below the shared CAN safety ceiling, while commit gives all
changed tracks one device-local start time while unchanged tracks retain their phase. Malformed or unsupported commands are ignored; there is
deliberately no acknowledgement layer.

The provisional bench Servotronic link uses ISO-TP IDs `0x70A`/`0x70B`. Its
fixed v1 request atomically installs the schema-v1 eight-point steering curve
in controller RAM after version, grid, bounds, monotonicity, and CRC-32 checks.
Status reports identify the built-in fallback or coordinator-supplied RAM curve
by activation revision and CRC. Curves are not persisted in EEPROM.

BMW message definitions remain unverified until backed by a named capture in
`docs/candump_sessions/` and recorded in `docs/decoded_messages.md`.

## Frontend contracts

FastAPI routes and Pydantic models are the source of truth for two browser contracts.
`openapi.json` describes the coordinator, including its multiplexed `GET /api/live` event union.
`console-openapi.json` independently describes the console host and its complete
`console.snapshot` stream. Hey API generates each TypeScript client, types and Zod validators.

The OpenAPI documents and TypeScript outputs under
`frontend/packages/coordinator-client/src/api/http/` and
`frontend/apps/console/src/api/console-host/` are committed generated artifacts. Never edit them by
hand. From `frontend/`, use `pnpm api:generate` to regenerate both paths in dependency order and
`pnpm api:check` for the non-mutating drift check used by CI. No backend process or hardware is
needed.

The OpenAPI document deliberately describes the simulator deployment, which is the superset of the
HTTP surface. Generated methods therefore do not prove that a car or bench deployment exposes a
simulator-only capability; the UI must still respect the deployment capabilities reported at
runtime.

The custom CAN device registry and codecs remain backend and firmware concerns while their physical
consumers still use them. They are not part of either browser stream. `buttons.program` remains the
canonical controller-requested device program; a successful send is not an acknowledgement or
evidence of physical output application.

`buttons.program.commands` are the exact ordered command bytes sent to the device, and `generation` is the
buttons-topic revision at which it changed. The browser observer renders those opaque wire bytes
through a replaceable renderer. Animation opcodes therefore do not expand the live-state contract;
the TypeScript renderer currently mirrors the firmware's fixed integer triangle wave and may later
be replaced by a WASM implementation. This remains requested state, not confirmation of physical
output application.

The controller constructs a canonical encoded `ButtonPadProgram` once through an opcode-specific
factory. Runtime effects and snapshots carry that immutable value; CAN output and live publication
forward its bytes without reconstructing or re-encoding the selected effect. Normative vectors in
`protocol/test-vectors/button-pad-program-v2.json` are consumed by the Python codec, TypeScript
renderer, and native C++ firmware-renderer tests.

The coordinator `health` projection contains readiness and fatal truth, explicit network, device
and steering faults, current inbox bounds and latency, overflow truth, and persistence status.
Publication is coalesced to 1 Hz. Reconnecting clients receive current health inside the complete
`snapshot` event.
