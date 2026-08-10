# Workstream 3: Prove the console CAN activity path end to end

Status: not started.

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

- Base commit: `TBD`
- Outcome: `TBD`
- Files changed: `TBD`
- Decisions: `TBD`
- Generated artifacts: `TBD`
- Verification: `TBD`
- Known limitations or external checks: physical SocketCAN/listen-only verification deferred to
  workstream 4 and hardware validation
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
