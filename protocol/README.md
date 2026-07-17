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

The button-pad RGB snapshot is a 48-byte ISO-TP payload on `0x708`/`0x709`, ordered as 16 `R G B`
triples. Consumers replace all values only after complete reassembly and exact-length validation.
Physical NeoTrellis rendering, mapping, brightness, and electrical limits remain deferred.

BMW message definitions remain unverified until backed by a named capture in
`docs/candump_sessions/` and recorded in `docs/decoded_messages.md`.

`live-events-v1.schema.json` is the generated Pydantic-owned Socket.IO payload schema. Run
`uv run python scripts/generate_live_contract.py` after changing a live payload model and use
`--check` in verification. The explicit TypeScript event map in
`frontend/src/api/live-events.ts` is checked against the schema's fixed event names; it contains
transport types only and does not duplicate controller behavior or CAN constants.

The device-registry phase owns the static role vocabulary and wire codecs. The current adapter
projection remains a temporary pre-registry transport surface until the registry kernel and live
contract phases replace it. `buttons.led_rgb` remains the canonical controller-requested LED
state; a successful send is not an acknowledgement or evidence of physical output application.

`controller.health` is a bounded, process-local operational projection rather than durable event
history or arbitrary logs. It contains readiness and fatal truth, explicit capability faults,
current inbox bounds/latency/overflow state, persistence status, and publisher failure,
trace/resource-drop and slow-client-isolation counters. Network availability and selected device
evidence remain in `devices.state`. Publication is coalesced to 1 Hz; reconnecting clients receive
the current complete health state in `controller.snapshot`. A service-only change advances both the
global envelope revision and health topic revision, so an already-synchronized client applies
persistence, readiness and decision-useful publisher changes without a controller input.
