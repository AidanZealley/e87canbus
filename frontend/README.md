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
Initial API startup and WebSocket failures retry automatically. WebSocket retries use jittered
exponential backoff, and the connection is resynchronised from the backend's full initial snapshot
after every reconnect. A heartbeat detects silent connections that stop delivering messages.

The workbench displays the isolated K-CAN, PT-CAN, and F-CAN topology plus one chronological trace.
Network filtering is local UI state and remains selected when the simulator is reset.

## Steering curve editor

The settings section keeps three values explicit: the browser draft, the coordinator's active
definition and the selected saved SQLite profile. Dragging, keyboard changes and numeric changes
edit the draft only. **Apply draft** changes simulator runtime state; **Save revision** and **Save
as** change the saved catalog. Loading or deleting a saved profile never applies it.

Curve points use the fixed schema-version-1 speed grid. Both `linear-v1` and
`monotone-cubic-v1` use the same pure TypeScript evaluator as the numeric preview. The chart samples
that evaluator once per draft change on a deterministic 1 km/h grid, renders those samples with
linear SVG paths and keeps the original points as separate handles in a layer above both curves.
The checked-in language-neutral vectors also drive the Python coordinator tests.

**Convert draft to smooth** changes only the interpolation discriminator in browser draft state.
It is available only when the runtime advertises `monotone-cubic-v1`; saving that draft creates an
explicit profile revision or new profile, and Apply remains a separate conscious activation. A
dirty draft is retained across WebSocket reconnects and external active changes; profile revision
conflicts retain it until the operator explicitly loads refreshed saved values. These profile
operations remain simulation-only and grant no physical output authority.

## Structure

- `src/api/` — HTTP and WebSocket simulator client.
- `src/components/steering-curve-editor/` — draft/active/saved curve editing and profile actions.
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
pnpm test
pnpm typecheck
pnpm build
```
