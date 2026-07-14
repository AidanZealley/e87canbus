# Phase 1: Routing and layout foundations

## Goal

Introduce TanStack Router file-based routing, preserve the simulator workbench at `/dev`, add the
development mode chooser and establish the isolated `/car` navigation shell. This phase creates
route and layout boundaries but does not build final telemetry instruments or settings forms.

## Dependencies and files to inspect

Before designing changes, inspect:

- `frontend/package.json`, lockfile and Vite configuration.
- `frontend/src/main.tsx`, `App.tsx` and `index.css`.
- The existing theme provider and simulator toolbar.
- `frontend/AGENTS.md` and installed shadcn primitives.
- Current TanStack Router file-based Vite documentation if package APIs have changed.

## Dependency and Vite setup

- Add `@tanstack/react-router` as a runtime dependency.
- Add `@tanstack/router-plugin` as a development dependency.
- Add the TanStack router Vite plugin before the React plugin:

```ts
tanstackRouter({
  target: "react",
  autoCodeSplitting: true,
})
```

- Retain the Tailwind Vite plugin and existing path alias.
- Use the defaults `src/routes` and `src/routeTree.gen.ts`.
- Exclude the generated route tree from ESLint and Prettier. Never hand-edit it.

## Router composition

Create `src/router.tsx` that:

- Imports the generated route tree.
- Calls `createRouter` with `defaultPreload: "intent"` and `scrollRestoration: true`.
- Registers the router through the `@tanstack/react-router` `Register` interface.

Change `main.tsx` to render `RouterProvider`. Keep `QueryClientProvider` and `ThemeProvider` above
the router so both application sections share the existing caches and theme. Remove `App.tsx` only
after no imports remain.

## Required route tree

```text
src/routes/
├── __root.tsx
├── index.tsx
├── dev/
│   ├── route.tsx
│   └── index.tsx
└── car/
    ├── route.tsx
    ├── index.tsx
    ├── drive/
    │   └── index.tsx
    ├── steering/
    │   └── index.tsx
    └── settings/
        └── index.tsx
```

Every route component should use `createFileRoute`; `__root.tsx` uses the root-route API. Directory
`route.tsx` files own layout and render `<Outlet />`.

## Root and not-found behavior

The root layout should impose no dev- or car-specific chrome. Its not-found component inspects the
requested location:

- An unknown `/car/*` path offers only a link to `/car`.
- All other unknown paths offer the chooser and `/dev`.
- Do not silently redirect, because the invalid URL is useful diagnostic evidence.

## Mode chooser

The `/` route is a development convenience, not an in-car navigation surface. Build a
full-viewport split layout with one router link for Development Workbench and one for Car Display.
Each half has an icon, title, short purpose statement and clear keyboard focus/hover state. Stack
the choices vertically when the viewport is too narrow. Use theme tokens and existing typography;
do not show `ModeToggle` here.

## Development layout

- `/dev/index.tsx` renders the existing `SimulatorWorkbench` without duplicating it.
- `/dev/route.tsx` is the future development-layout boundary and currently renders its outlet.
- Add a home icon router link to `/` in the simulator toolbar.
- Add the shared theme control beside the other toolbar controls.
- Preserve current workbench max width, grids, connection behavior and desktop density.

## Shared mode toggle

Add a component following `frontend/AGENTS.md`:

```text
src/components/mode-toggle/
├── ModeToggle.tsx
└── index.ts
```

Install the shadcn dropdown-menu primitive using the configured CLI. Offer Light, Dark and System,
using the existing `useTheme` hook. Do not replace the current provider, storage validation,
system-theme listener or keyboard shortcut. The control appears in the dev toolbar now and in the
car settings page during Phase 6.

## Car layout shell

Build an `h-svh`, 800x480-landscape-first layout with an always-visible icon-only rail. Links are
ordered:

1. Overview: `/car`
2. Drive: `/car/drive`
3. Steering: `/car/steering`
4. Settings: `/car/settings`

Every link needs an accessible label, visible focus state, tooltip/title and active state. The rail
must not render a route to `/`, `/dev`, router tooling or theme control. Control sizing follows
normal component variants and available space; do not encode a global pixel-size rule.

Provide a content area and placeholders/outlets for later phases. Reserve a compact top-edge region
for the connection banner without implementing invented telemetry state. Direct loading and browser
refresh must work for every car route through Vite history fallback.

## Styling constraints

- Use existing shadcn tokens or named Tailwind colors.
- Do not make global body rules car-specific.
- Keep dev and car layout styles within their respective components/routes.
- Avoid horizontal document overflow at 800x480.
- Do not add fixed-control-size tests. Physical touch tuning is a later manual activity.

## Tests

- Generated routes typecheck and build.
- `/` renders both mode links.
- `/dev` renders the existing workbench.
- Every `/car` child renders inside the car layout.
- Car navigation has accessible names and correct active state.
- No `/car` layout link targets `/` or `/dev`.
- Unknown car routes expose only car-safe recovery navigation.
- Other unknown routes expose chooser/development recovery.
- Dev toolbar exposes home and theme controls.
- Theme selection still updates the root class and persists through the existing provider.

## Completion criteria

- The route structure is generated and type-safe.
- Existing workbench behavior is preserved at `/dev`.
- Direct navigation and refresh work for every declared route.
- The root chooser and isolated car rail match the specified navigation policy.
- The generated file is excluded from formatting/lint ownership.
- No final telemetry, settings or steering behavior has been faked to complete the shell.

