# Workstream 2: Split the frontend into two ordinary applications

Status: not started.

## Task packet

### Outcome

`frontend` is a pnpm workspace with independently buildable coordinator and console Vite apps.
Existing `/dev` content belongs to the coordinator app, existing `/car` content belongs to the
console app, and both consume one shared coordinator API/client implementation without a shared UI
framework.

### Scope

- Create `frontend/apps/coordinator`, `frontend/apps/console` and
  `frontend/packages/coordinator-client` using the existing Vite/React structure.
- Move the workbench, simulation and coordinator-management routes/components into the coordinator
  app and make coordinator content its root experience.
- Move the existing car layout, overview, drive, steering and settings content into the console
  app and make former `/car` content its root experience with the existing child screens.
- Remove the combined mode-chooser route and obsolete `/dev`/`car` prefix assumptions rather than
  preserving compatibility routes.
- Move generated OpenAPI and coordinator Socket.IO types plus coordinator HTTP/live client state
  and transport code used by both apps into `coordinator-client`.
- Keep application-owned components, routes, themes and UI primitives in their owning app. Copy a
  small primitive only when moving it is simpler than creating a package; do not create a design
  system.
- Give the workspace root aggregate install, generation, dev, lint, test, type-check and build
  scripts, plus usable filtered app commands.
- Update contract generators/watchers and CI for the workspace locations and single generated
  coordinator-client source of truth.
- Preserve current UI behaviour and tests while dividing them by app ownership.

### Non-goals

- Adding the local console CAN Socket.IO contract, store or activity UI; workstream 3 owns that
  vertical slice.
- Redesigning either application or changing settings behaviour.
- Introducing Nx, Turborepo, micro-frontends, runtime app selection or a generalized app shell.
- Creating a shared UI/design-system package.
- Duplicating generated API contracts, coordinator Zustand authority or coordinator Socket.IO
  transport between apps.
- Changing backend API behaviour.

### Initial ownership

- `frontend/**`
- Frontend-related sections of `.github/workflows/ci.yml` transferred from workstream 1
- `scripts/generate_openapi.py`, `scripts/generate_live_contract.py` and
  `scripts/watch_frontend_contracts.py` only for new output/workspace paths
- Generated `protocol/openapi.json` and `protocol/live-events-v1.schema.json` only if their source
  schema genuinely changes; path-only work should leave their content unchanged

Do not edit host application behaviour under `hosts/src/e87canbus`.

### Required seams

- Workspace directories and coordinator-client ownership match [plan.md](plan.md).
- `coordinator-client` contains no React views or app-specific routing.
- Production builds are separately addressable as `frontend/apps/coordinator/dist` and
  `frontend/apps/console/dist` for workstream 4.
- The console app can configure its coordinator origin independently of its own serving origin;
  workstream 3 will add a second local live source.
- Generated artifacts remain committed and drift-checkable from the workspace root.

### Acceptance criteria

- A clean install can build either app independently and both through aggregate workspace scripts.
- The coordinator app contains no driver-layout route bundle; the console app contains no
  workbench, simulator or detailed engineering route bundle.
- The old chooser and combined app entry point are deleted.
- Existing workbench and car-screen behaviour remains protected by meaningful tests in the owning
  apps.
- Both apps consume the same generated coordinator contracts and coordinator live client/store.
- No shared package contains code used by only one app.
- Vite, TypeScript, ESLint, Vitest and Tailwind configuration is direct and understandable without
  a new monorepo framework.

### Targeted verification

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm api:check
pnpm --filter ./apps/coordinator typecheck
pnpm --filter ./apps/coordinator test
pnpm --filter ./apps/coordinator build
pnpm --filter ./apps/console typecheck
pnpm --filter ./apps/console test
pnpm --filter ./apps/console build
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Run the route/component tests moved into each app and inspect both Vite build manifests or output
chunks to confirm the prohibited cross-app feature sets are absent.

## Implementation handoff

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Verification: `TBD`
- Known limitations or external checks: `TBD`
- Specification drift: `TBD`

## Independent review

- Reviewer: `TBD`
- Verdict: `TBD`
- Required findings: `TBD`
- Optional observations: `TBD`
- Questions for orchestrator: `TBD`

## Resolution

- Finding dispositions: `TBD`
- Simplification/deletion pass: `TBD`
- Final verification: `TBD`

## Closure review

- Verdict: `TBD`
- Remaining required findings: `TBD`
- Accepted commit: `TBD`

