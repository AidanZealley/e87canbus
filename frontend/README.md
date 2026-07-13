# Frontend

React UI for the hardware-free simulator workbench and future in-car display.

## Stack

- Vite 8
- React 19
- Tailwind CSS 4
- shadcn/ui with Base UI and the project Mira/Mist preset
- TypeScript 6

## Development

Start the simulator API from the repository root, then the frontend:

```bash
uv run e87canbus-sim-api --reload
cd frontend
pnpm install
pnpm dev
```

The frontend defaults to `http://127.0.0.1:5173` and expects the API at
`http://127.0.0.1:8000`. Override these with `VITE_API_BASE` and `VITE_WS_BASE`.

## Structure

- `src/api/` — HTTP and WebSocket simulator client.
- `src/components/simulator-workbench/` — workbench composition and feature components.
- `src/components/ui/` — shadcn component source managed with the shadcn CLI.
- `src/lib/` — shared utilities.

Follow `AGENTS.md` when adding project components. Use the shadcn CLI with pnpm
when adding or updating UI primitives:

```bash
pnpm dlx shadcn@latest add <component>
```

## Verification

```bash
pnpm lint
pnpm typecheck
pnpm build
```
