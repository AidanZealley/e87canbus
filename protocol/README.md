# Protocol

Cross-device CAN protocol documentation and vehicle DBC material live here. Firmware and
coordinator implementations must agree with these definitions.

`custom.toml` is the source of truth for the provisional project messages. Run
`uv run python scripts/generate_custom_protocol.py` from the repository root to update the Python
constants, button-pad header, and generated section of `custom_ids.md`; use `--check` in verification.

Incoming definitions are scoped by logical network as well as arbitration ID. The current custom
`0x700`/`0x701` messages are provisional K-CAN bench/simulation definitions and need collision
validation before vehicle use.

BMW message definitions remain unverified until backed by a named capture in
`docs/candump_sessions/` and recorded in `docs/decoded_messages.md`.
