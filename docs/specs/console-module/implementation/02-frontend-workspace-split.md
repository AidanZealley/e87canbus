# Workstream 2: Split the frontend into two ordinary applications

Status: closure review.

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

- Base commit: `95c33b0676a063b8e3fcbc253ec8bad6dbce0c8c`
- Outcome: Split the combined frontend into independently rooted coordinator and console Vite
  applications in one pnpm workspace. The chooser and `/dev`/`/car` prefixes are gone, and both
  apps consume one UI-free coordinator HTTP/Socket.IO client package.
- Files changed: Moved coordinator-owned routes, workbench components, UI primitives and config to
  `frontend/apps/coordinator`; moved the existing driver layout and screens plus their app-owned
  primitives to `frontend/apps/console`; moved generated contracts, HTTP configuration, live
  transport/stores and application-settings query authority to
  `frontend/packages/coordinator-client`. Updated workspace manifests/lockfile, generator paths,
  lint/format configuration and the frontend README.
- Decisions: Kept ordinary duplicated app configuration, theme CSS and UI primitives instead of
  introducing shared Vite or design-system packages. Both apps start the same coordinator client;
  `VITE_COORDINATOR_ORIGIN` lets the console target the coordinator independently of its serving
  origin. CI's existing root frontend commands remain the aggregate workspace checks, while
  filtered `dev`, `build`, `test` and `typecheck` commands address each app directly.
- Verification: `pnpm install --frozen-lockfile`, app-filtered and aggregate typechecks, ESLint,
  app-filtered tests (coordinator 89, console 86), coordinator-client tests (18), aggregate tests
  (193 total), both filtered builds and the aggregate build passed. Direct OpenAPI/live Python
  drift checks, `pnpm http:check`, the TypeScript live-contract check and `git diff --check`
  passed. Built-output string/chunk inspection found no driver-layout markers in coordinator
  output and no workbench/simulator markers in console output.
- Known limitations or external checks: The literal `pnpm api:check` wrapper cannot run because
  `uv` is unavailable in this shell; all of its constituent checks passed using the existing
  virtual environment with `hosts/src` on `PYTHONPATH`. No browser/device visual check was run;
  existing route and component tests protect the mechanical UI split.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws2_reviewer`)
- Verdict: Changes required. The workspace split, ownership boundaries, root-relative routes,
  single generated coordinator-client source, configurable production coordinator origin and
  separate build artifacts otherwise satisfy the packet. Independent verification passed the
  frozen install, both filtered typechecks/tests/builds, aggregate typecheck/lint/test/build (193
  tests), HTTP and live TypeScript drift checks, direct Python OpenAPI/live drift checks and
  `git diff --check`. Output inspection found no console/driver markers in the coordinator build
  and no workbench/simulator markers in the console build; a console build with
  `VITE_COORDINATOR_ORIGIN=http://10.43.0.1` embeds that independent origin.
- Required findings: The documented development path cannot connect the console app to the
  coordinator. `apps/console/package.json` serves it on port 5174 and the shared client defaults
  to `http://127.0.0.1:8000`, but `hosts/src/e87canbus/api/main.py` permits only localhost and
  127.0.0.1 port 5173 by default for both HTTP CORS and Socket.IO. `frontend/README.md` starts the
  simulator without an additional `--cors-origin`, then advertises the console at 5174. Thus the
  ordinary aggregate and filtered console dev commands produce an origin the coordinator rejects.
  Resolve this at the frontend development/configuration seam (without broadening production or
  changing backend API behaviour), and protect the resulting console dev origin path with a
  focused configuration test or equivalent drift check.
- Optional observations: None.
- Questions for orchestrator: None.

## Resolution

- Finding dispositions: Accepted the console-development origin finding. The fixed console dev
  server now uses `http://localhost:5174` as its coordinator origin and proxies `/api`, `/health`
  and `/socket.io` to the loopback backend. Only that frontend proxy hop rewrites `Origin` to the
  backend's already permitted `http://127.0.0.1:5173`; backend HTTP CORS and Socket.IO policy are
  unchanged. Production continues to use an independently supplied `VITE_COORDINATOR_ORIGIN` or
  the console's serving origin.
- Simplification/deletion pass: Kept the fix entirely in the console Vite configuration and one
  development environment file. Removed the duplicated CLI port argument, used one small local
  proxy constructor for the three coordinator paths and added no shared dev-server abstraction,
  backend exception or compatibility route.
- Final verification: The focused config test proves the fixed same-origin console port, complete
  coordinator HTTP/health/Socket.IO proxy surface, WebSocket proxying and allowed-origin rewrite.
  Console typecheck, 88 console tests and console production build passed; aggregate tests passed
  all 195 tests, ESLint and `git diff --check` passed.

## Closure review

- Verdict: Pass. The accepted finding is resolved entirely at the console development edge. A
  focused live run through `http://localhost:5174` returned the coordinator `/health/live`
  response and completed the Socket.IO polling handshake while the unchanged backend accepted the
  rewritten existing development origin. The two proxy configuration tests, console typecheck and
  production build passed. Default and `VITE_COORDINATOR_ORIGIN=http://10.43.0.1` production
  output inspection found no leaked localhost/loopback development proxy origin, and the configured
  build retained the independent coordinator address. `git diff --check` also passed. The fix adds
  only one app-local Vite proxy helper and its development environment value; it introduces no
  backend exception, compatibility route or shared abstraction.
- Remaining required findings: None.
- Accepted commit: `TBD`
