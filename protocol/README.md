# Protocol

The coordinator retains vehicle CAN frame values and simulation-only vehicle decoders. There is no project-device CAN protocol.

BMW message definitions remain unverified until backed by a named capture in docs/candump_sessions and recorded in docs/decoded_messages.md.

## Frontend contracts

FastAPI routes and Pydantic models are the source of truth for browser contracts. openapi.json describes the coordinator, including its multiplexed GET /api/live event union. console-openapi.json describes the console host and its complete console.snapshot stream. Hey API generates each TypeScript client, types, and Zod validators.

The OpenAPI documents and TypeScript outputs are committed generated artifacts. From frontend, run pnpm api:generate to regenerate them and pnpm api:check to check for drift.

The coordinator OpenAPI document describes the simulator deployment, which has more HTTP routes than car or bench. Check deployment capabilities before showing simulation controls. Browser live buttons state carries the active profile identity and revision, never device program bytes.
