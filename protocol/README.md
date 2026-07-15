# Protocol

Cross-device CAN protocol documentation and vehicle DBC material live here. Firmware and
coordinator implementations must agree with these definitions.

`custom.toml` is the source of truth for the provisional project messages. Run
`uv run python scripts/generate_custom_protocol.py` from the repository root to update the Python
constants, button-pad header, and generated section of `custom_ids.md`; use `--check` in verification.

Incoming definitions are scoped by logical network as well as arbitration ID. The current custom
`0x700`/`0x701` messages are provisional K-CAN bench/simulation definitions and need collision
validation before vehicle use.

`0x701` has DLC 8 and carries the complete 16-colour button-pad LED state, with the even logical
position in each byte's low nibble and the following odd position in its high nibble. Codes above
`0x5`, the wrong arbitration ID, or any length other than eight are not a snapshot. Consumers
validate the entire frame before replacing all 16 logical colours; no prefix is applied. Physical
NeoTrellis topology, mapping, brightness, and electrical limits remain unselected pending verified
hardware evidence.

BMW message definitions remain unverified until backed by a named capture in
`docs/candump_sessions/` and recorded in `docs/decoded_messages.md`.

`live-events-v1.schema.json` is the generated Pydantic-owned Socket.IO payload schema. Run
`uv run python scripts/generate_live_contract.py` after changing a live payload model and use
`--check` in verification. The explicit TypeScript event map in
`frontend/src/api/live-events.ts` is checked against the schema's fixed event names; it contains
transport types only and does not duplicate controller behavior or CAN constants.

The `devices.state` button-pad projection identifies its selected physical, emulated, or observer
source and keeps controller-desired LEDs separate from device-observed LEDs. Emulator observation
means its decoder received a valid complete `0x701` frame. Physical connection and observation stay
unknown until the wire protocol supplies evidence; a successful send is not an acknowledgement.

`controller.health` is a bounded, process-local operational projection rather than durable event
history or arbitrary logs. It contains readiness and fatal truth, explicit capability faults,
current inbox bounds/latency/overflow state, persistence status, and publisher failure,
trace/resource-drop and slow-client-isolation counters. Network availability and selected device
evidence remain in `devices.state`. Publication is coalesced to 1 Hz; reconnecting clients receive
the current complete health state in `controller.snapshot`. A service-only change advances both the
global envelope revision and health topic revision, so an already-synchronized client applies
persistence, readiness and decision-useful publisher changes without a controller input.
