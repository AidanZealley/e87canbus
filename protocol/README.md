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
