# Protocol

custom.toml defines the remaining provisional Servotronic CAN messages. Run uv run python scripts/generate_custom_protocol.py from the repository root to update Python constants, the Servotronic firmware header, and the generated table in custom_ids.md. Use --check to verify them.

The Servotronic registry uses K-CAN IDs 0x705 through 0x707 for HELLO, WELCOME_ACK, and HEARTBEAT. All have DLC 8 and unsigned little-endian multi-byte fields. The bench-only curve and status ISO-TP link uses 0x70A and 0x70B. These IDs need collision validation before vehicle use. The protocol is removed in Slice 1.5 Workstream 3.

BMW message definitions remain unverified until backed by a named capture in docs/candump_sessions and recorded in docs/decoded_messages.md.

## Frontend contracts

FastAPI routes and Pydantic models are the source of truth for browser contracts. openapi.json describes the coordinator, including its multiplexed GET /api/live event union. console-openapi.json describes the console host and its complete console.snapshot stream. Hey API generates each TypeScript client, types, and Zod validators.

The OpenAPI documents and TypeScript outputs are committed generated artifacts. From frontend, run pnpm api:generate to regenerate them and pnpm api:check to check for drift.

The coordinator OpenAPI document describes the simulator deployment, which has more HTTP routes than car or bench. Check deployment capabilities before showing simulation controls. Browser live buttons state carries the active profile identity and revision, never device program bytes.
