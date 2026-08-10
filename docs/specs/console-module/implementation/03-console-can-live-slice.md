# Workstream 3: Prove the console CAN activity path end to end

Status: closure review.

## Task packet

### Outcome

A small console host service opens one injected receive-only K-CAN endpoint, counts received frames
and serves the console app plus a bounded `console.snapshot` Socket.IO stream. The console React app
shows K-CAN connection/activity through a generated contract, one local transport and one small
Zustand store. The slice works without the coordinator or Ethernet.

### Scope

- Add `e87canbus.console` under the accepted host package with a dedicated console CLI entry point,
  lifecycle, app factory and injected `CanReceiver` boundary.
- Reuse `CanFrame`, `CanReceiver` and `SocketCanBus` directly. Do not give the console a transmitter
  or reuse the coordinator kernel/runtime.
- Open, receive, count, fault, stop, join and close the CAN reader predictably with bounded state.
- Define the version-1 complete console live model and sole server event `console.snapshot` exactly
  as frozen in [plan.md](plan.md).
- Generate and commit a console live JSON schema and TypeScript event contract using the existing
  generation approach without generalizing the coordinator publisher.
- Send a complete snapshot on client connection, coalesce changed activity to at most 1 Hz and
  publish faults promptly. Use finite outbound client queues and keep CAN receipt independent of
  browser speed or failure.
- Serve the built console SPA locally and expose minimal liveness/readiness suitable for deployment.
- Add the console app's local Socket.IO singleton, protocol/boot/revision handling, Zustand store
  and one unobtrusive K-CAN connection/frame-count status view.
- Add focused backend, contract, transport, store and React tests, including a fake receiver frame
  reaching the rendered status.
- Extend aggregate generated-contract checks for the new console contract.

### Non-goals

- Decoding a BMW signal or adding a CAN-driven vehicle feature.
- Publishing arbitration IDs, DLCs, payload bytes or raw traces.
- Console CAN transmission, even as a disabled flag or unused method.
- Reusing `ControllerLoop`, `CoordinatorKernel`, coordinator topic revisions, trace subscription,
  resource invalidation or resynchronization machinery.
- Combining coordinator and console live state into one store.
- Implementing systemd, listen-only `ip` configuration, Ethernet or Pi setup; workstream 4 owns
  deployment enforcement.
- Creating a generic host/runtime/publisher framework for hypothetical roles.
- Adding a browser-automation or end-to-end test framework solely for this proof.

### Initial ownership

- `hosts/src/e87canbus/console/**`
- `hosts/tests/console/**`
- `pyproject.toml` only for the console entry point and required package dependencies/configuration
- Shared host web helpers only when existing code is already role-neutral and can be moved without
  changing coordinator behaviour
- Console contract generator source and its committed schema artifact
- Console-contract generation scripts/artifacts inside `frontend/apps/console`
- Console app local-live transport, store, status component and focused tests
- Workspace/CI aggregate contract commands only to include the new generated contract

Do not change coordinator control rules, coordinator live payloads or other console UI content.

### Required seams

- Event and payload shape, rate and production origins match [plan.md](plan.md).
- `connected` means the console service currently owns an open CAN receiver; it does not claim that
  vehicle traffic is healthy. `frames_received` resets with `boot_id` and increases for every
  successfully received frame. `fault` is nullable and diagnostic.
- A silent bus is distinct from reader failure. The UI may say no frames observed without declaring
  a CAN fault.
- Every snapshot is complete, so the local client can replace its state and ignore older revisions;
  it needs no topic-gap resync protocol.
- Browser disconnect, slow clients and publication failure cannot block or stop the CAN reader.
- The coordinator origin and local console origin remain separate connections and stores.

### Acceptance criteria

- Backend tests inject a receiver, observe frame count/revision changes, confirm bounded publication
  and prove clean shutdown/fault behaviour.
- Socket.IO tests receive an immediate complete snapshot and a coalesced changed snapshot.
- Generated Python/JSON/TypeScript contract representations agree and drift checks pass.
- Frontend tests cover connect, first-snapshot synchronization, boot change, stale revision,
  disconnect/fault presentation and rendered frame-count update.
- Focused backend and frontend tests collectively prove each seam from fake `CanFrame` reception to
  the rendered React status without embedding raw frame content in any public payload.
- Coordinator tests and live contract remain unchanged and passing.
- The implementation contains no transmitter, decoded BMW signal or generalized runtime layer.

### Targeted verification

```bash
uv run pytest -q hosts/tests/console hosts/tests/test_socketcan.py
uv run mypy
uv run ruff check hosts/src/e87canbus/console hosts/tests/console
uv run lint-imports
cd frontend
pnpm api:check
pnpm --filter ./apps/console typecheck
pnpm --filter ./apps/console test
pnpm --filter ./apps/console build
```

Also run the newly added backend-to-Socket.IO integration test and the focused React status test by
their final committed paths.

## Implementation handoff

- Base commit: `24db2295fea3ace35d620de5f0c3b5969f186e11`
- Outcome: Added a standalone `e87canbus-console` host service that owns one injected receive-only
  K-CAN endpoint, publishes the complete bounded `console.snapshot` model and serves the console
  SPA. The console app now ingests that local event through its own Socket.IO transport and Zustand
  store and renders connection, silence, frame-count and fault status independently of coordinator
  state.
- Files changed: Added `hosts/src/e87canbus/console/**` and focused
  `hosts/tests/console/**`; moved the existing role-neutral bounded Socket.IO server and SPA fallback
  into `e87canbus.adapters` and updated their coordinator imports; added the console CLI entry point;
  added the console schema generator/artifact; added the console app-local generator, contract,
  transport, store, status component and focused tests; updated the console/workspace manifests,
  lockfile and aggregate live-contract commands.
- Decisions: Kept one reader thread and one immutable five-field service snapshot instead of
  introducing a console runtime/kernel. The injected boundary exposes receive and lifecycle close
  only even though production composes the existing `SocketCanBus`. Publisher wakeups and retained
  activity are latest-state coalesced, broadcasts are limited to one per second, faults bypass that
  interval, sends have a deadline and each Engine.IO peer has a finite eight-packet queue. The local
  client uses same-origin Socket.IO and complete-snapshot boot/revision replacement with no resync,
  topic or coordinator-store machinery.
- Generated artifacts: `protocol/console-live-v1.schema.json` from
  `scripts/generate_console_live_contract.py`; and
  `frontend/apps/console/src/local-live/contract.gen.ts` from the console app-local generator.
- Verification: 15 focused console/SocketCAN/bounded-queue tests passed, including the fake-frame
  backend-to-Socket.IO test; 75 existing coordinator live/publication/simulator contract tests
  passed, and the complete 832-test Python suite passed; strict mypy over 130 source files, Ruff and
  both import-linter contracts passed. Console typecheck, 96 console tests including the rendered
  status proof, production build and aggregate ESLint passed. Direct Python/Node OpenAPI, HTTP,
  coordinator-live and console-live drift checks passed, as did `git diff --check`. The literal
  `uv run` wrappers were unavailable in this shell; their checks ran through the existing locked
  environment with `hosts/src` on `PYTHONPATH`.
- Known limitations or external checks: physical SocketCAN/listen-only verification deferred to
  workstream 4 and hardware validation. No physical CAN interface or browser/device visual check
  was available here.
- Specification drift: None.

## Independent review

- Reviewer: Codex (`/root/ws3_reviewer`)
- Verdict: Changes required. The backend service, exact generated envelope, boot/revision rules,
  latest-state publication, prompt faults, bounded Engine.IO queues, lifecycle/health endpoints and
  local Zustand/status path otherwise satisfy the packet without raw CAN, transmit capability or a
  generalized runtime. Independent verification passed 15 focused Python tests, focused mypy and
  Ruff, console typecheck, all 96 console tests, the console production build, direct Python and
  TypeScript console-contract drift checks, the existing coordinator TypeScript live-contract
  check and `git diff --check`. The aggregate `pnpm live:check` wrapper reached its expected local
  environment limitation because `uv` is unavailable; its relevant checks passed directly through
  the locked environment.
- Required findings: The maintained console development path routes both Socket.IO clients to the
  coordinator, so the new local connection cannot receive `console.snapshot`. Specifically,
  `.env.development` makes the coordinator client use `http://localhost:5174`, the Vite server
  proxies the sole `/socket.io` path to `http://127.0.0.1:8000`, and the local transport also calls
  `io()` on the Vite origin's default `/socket.io` path. Thus `pnpm dev:console`, which the frontend
  README advertises, sends both independently owned socket instances to the coordinator service;
  running the local console service cannot supply the React CAN activity slice through that route.
  Give the local and coordinator Socket.IO paths/origins unambiguous app-local routing in
  development, while retaining loopback production hosting and the independently configured
  coordinator origin, and add a focused configuration/transport test that protects the routing
  seam.
- Optional observations: None.
- Questions for orchestrator: None.

## Resolution

- Finding dispositions: Accepted. Console-local Socket.IO now owns the explicit
  `/console/socket.io` path in both production and development. The console Vite server proxies
  only that path to the local console service on `127.0.0.1:8001`; coordinator HTTP and
  `/socket.io` continue to proxy independently to `127.0.0.1:8000`. The maintained development
  instructions now start both backend processes.
- Simplification/deletion pass: Kept one app-local path constant shared by the local transport and
  Vite configuration, two direct role-named proxy definitions and the backend's matching Socket.IO
  mount. Added no generic origin/router configuration, compatibility path or new environment
  variable; production coordinator-origin configuration remains unchanged.
- Final verification: The focused Vite configuration test proves distinct paths, targets,
  WebSocket proxying and exact origin rewrites, while the transport test protects use of the local
  path. Console typecheck and all 97 console tests passed; 15 focused Python tests, strict mypy,
  Ruff, console production build, aggregate ESLint and `git diff --check` passed. A live Vite
  development run completed an Engine.IO polling handshake through
  `http://localhost:5174/console/socket.io` to the console service on port 8001; the service
  correctly remained live and reported the expected missing-`kcan` fault in this environment.

## Closure review

- Verdict: Pass. The accepted routing collision is resolved with one explicit
  `/console/socket.io` path shared by the local browser transport and console backend. In
  development, Vite proxies only that path to the loopback console service on port 8001 while the
  unchanged coordinator `/socket.io`, HTTP and health paths remain on port 8000; production embeds
  the same relative local path and retains the independently configured coordinator origin. The
  focused Vite and transport tests passed, as did all 15 focused Python tests, console typecheck,
  production build and `git diff --check`. An independent live Engine.IO polling handshake through
  `http://127.0.0.1:5174/console/socket.io` reached the console service on port 8001. The direct
  role-named proxies and one small path constant introduce no compatibility route, generalized
  runtime or speculative routing machinery.
- Remaining required findings: None.
- Accepted commit: Pending post-closure implementation commit.
