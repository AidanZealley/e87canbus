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
track: solid, blink, breathe, or travelling gradient; RGB, two kind-specific parameters, `repeat`,
and final RGB. A travelling gradient uses its RGB and final RGB as cyan/pink-style endpoints, a
bounded period, and a direction value (currently `1`, north-west-to-south-east) with device-local
4×4 coordinates, so it does not consume
per-frame CAN traffic. A repeat
of zero runs forever and a positive repeat count finishes on final RGB. The controller resolves the
base scene before encoding, so the AVR stores exactly one fixed-size base track per button. A
single-frame command on `0x701` starts finite red feedback or enables/disables a per-button breathe
overlay without replacing that base scene. Commands are paced below the shared CAN safety ceiling, while commit gives all
changed tracks one device-local start time while unchanged tracks retain their phase. Malformed or unsupported commands are ignored; there is
deliberately no acknowledgement layer.

BMW message definitions remain unverified until backed by a named capture in
`docs/candump_sessions/` and recorded in `docs/decoded_messages.md`.

## Frontend contracts

Python is the source of truth for both frontend transport contracts. FastAPI routes and Pydantic
models generate the canonical simulator-superset `openapi.json`; the backend event registry owns
every Socket.IO event name, direction and exact argument type and generates
`live-events-v1.schema.json`. Runtime publication and handlers consume that same event registry.

The schemas in this directory and the TypeScript outputs in `frontend/src/api/http/` and
`frontend/src/api/live-contract.gen.ts` are committed generated artifacts. Never edit them by hand.
From `frontend/`, use `pnpm api:generate` to regenerate all four artifacts in dependency order and
`pnpm api:check` to check them without changing the worktree. The narrower `http:*` and `live:*`
commands are available when working on only one contract. No backend process or hardware is needed.

The OpenAPI document deliberately describes the simulator deployment, which is the superset of the
HTTP surface. Generated methods therefore do not prove that a car or bench deployment exposes a
simulator-only capability; the UI must still respect the deployment capabilities reported at
runtime.

The device-registry phase owns the static role vocabulary and wire codecs. The current adapter
projection remains a temporary pre-registry transport surface until the registry kernel and live
contract phases replace it. `buttons.program` remains the canonical controller-requested device
program; a successful send is not an acknowledgement or evidence of physical output application.

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

`controller.health` is a bounded, process-local operational projection rather than durable event
history or arbitrary logs. It contains readiness and fatal truth, explicit capability faults,
current inbox bounds/latency/overflow state, persistence status, and publisher failure,
trace/resource-drop and slow-client-isolation counters. Network availability and selected device
evidence remain in `devices.state`. Publication is coalesced to 1 Hz; reconnecting clients receive
the current complete health state in `controller.snapshot`. A service-only change advances both the
global envelope revision and health topic revision, so an already-synchronized client applies
persistence, readiness and decision-useful publisher changes without a controller input.
