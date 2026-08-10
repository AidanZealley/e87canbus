# Coordinator and console split implementation plan

Status: implementation in progress.

## Orchestration record

- Integration branch: `feature/coordinator-console-split`
- Starting commit: `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`
- Orchestrator: Codex (`/root`)
- Specification approved at commit: `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`
- Started: `2026-08-10`

## Workstream order

| # | Workstream | Depends on | Status | Accepted commit |
|---:|---|---|---|---|
| 1 | [Role-neutral host project](01-host-project-layout.md) | Approved spec | Accepted | `5c1afaf1a73457ebc04f01060ffceaa9ac0befe7` |
| 2 | [Two-app frontend workspace](02-frontend-workspace-split.md) | Workstream 1 | Accepted | `309fa33987f81fd5c029c6cb087911befb84705a` |
| 3 | [Console CAN activity vertical slice](03-console-can-live-slice.md) | Workstreams 1–2 | Accepted | `5013093ba80fa22a03f405482248a3212c21e5d8` |
| 4 | [Coordinator and console deployment](04-host-deployment.md) | Workstreams 1–3 | Not started | — |
| 5 | [Documentation and architectural record](05-documentation.md) | Workstreams 1–4 | Not started | — |

Use only `Not started`, `Implementing`, `Review`, `Remediation`, `Closure review` and `Accepted`.
At most one workstream may be active. This deliberate sequence avoids path-move and generated-file
conflicts; expected latency savings do not justify concurrent edits to the shared worktree.

## Why these boundaries

1. The host-project rename is a mechanical foundation and makes every later task use final Python
   paths without mixing the move with new behaviour.
2. The frontend split is another behaviour-preserving move. It freezes app/package ownership and
   build commands before the console slice or deployment consumes them.
3. The CAN activity proof is one vertical product slice from SocketCAN through the local backend
   contract to React. Keeping backend and frontend together prevents contract handoff ambiguity.
4. Setup, systemd, kiosk and Ethernet form one distinct Raspberry Pi deployment edge and consume
   already accepted entry points and build artifacts.
5. Documentation follows the finished paths and behaviour, so it can remove stale instructions
   rather than speculate about intermediate layouts.

## Cross-workstream contracts

- Python host code lives in `hosts/src/e87canbus`; tests live in `hosts/tests`. Existing import
  layers remain intact. New role-specific backend code uses `e87canbus.console`.
- `devices/` remains microcontroller firmware and is not reorganized.
- `frontend` is one pnpm workspace with `apps/coordinator`, `apps/console` and
  `packages/coordinator-client`. The package contains the single generated coordinator HTTP and
  Socket.IO contracts and the existing coordinator client state/transport code genuinely used by
  both apps; it contains no UI.
- The old combined route chooser is removed. Coordinator content is rooted in the coordinator app;
  former `/car` content is rooted in the console app with its existing child screens.
- The local console contract has one server event, `console.snapshot`, carrying a complete
  version-1 envelope with `boot_id`, monotonic `revision`, `emitted_at` and `data.can`. `data.can`
  contains only `interface: "kcan"`, `connected`, nonnegative `frames_received` and nullable
  `fault`. It never contains arbitration IDs or payload bytes.
- Console activity publication is latest-state coalesced to at most 1 Hz, plus an immediate full
  snapshot on client connection and prompt fault state. React receives it through one local
  Socket.IO transport and one small Zustand store.
- Production coordinator application remains on `127.0.0.1:8000`; its constrained console-link
  proxy is `10.43.0.1:80`. Production console service and frontend remain on
  `127.0.0.1:8000`. The console reaches the coordinator at `http://10.43.0.1`.
- Dedicated Ethernet is `10.43.0.0/30`: coordinator `.1`, console `.2`, no gateway, DNS or
  forwarding. Existing hotspot `10.42.0.0/24` remains separate.
- Console K-CAN is the HAT+ first controller mapped to logical `kcan`, configured at 100 kbit/s
  with kernel listen-only enabled. The second controller has no enabled service or connection.
- `scripts/setup_coordinator.sh` builds/hosts only the coordinator app;
  `scripts/setup_console.sh` builds/hosts only the console app. Host role is not a controller
  deployment profile.

Any defect in a frozen seam returns through the orchestrator to its owning workstream. Later agents
must not silently redesign it.

## Ownership handoffs

- Workstream 1 hands final host paths, Python tool configuration and CI host commands to every
  later stream.
- Workstream 2 hands workspace scripts, generated coordinator-client ownership, app roots and
  build artifact paths to workstreams 3–5.
- Workstream 3 hands the console Python entry point, local contract generator/artifacts, service
  health semantics and console build integration to deployment and documentation.
- Workstream 4 hands final scripts, units, network names, addresses, origin policy and operator
  commands to documentation.
- Files transferred sequentially may be edited by their later owner only for that later packet's
  integration needs; unrelated cleanup returns to the original owner.

## Whole-feature acceptance

Before final review:

- All five records show accepted commits and clean sequential heads.
- Normal Python, generated-contract, frontend and shell checks pass.
- Coordinator behaviour and safety boundaries remain unchanged.
- Both frontend apps build independently and aggregate workspace checks pass.
- Automated tests prove the console frame-to-Socket.IO-to-Zustand-to-React path without exposing
  raw CAN.
- Deployment configuration is statically verified; actual blank-Pi, direct-Ethernet, physical
  listen-only CAN and vehicle-power checks are explicitly pending hardware validation.
- Maintained documentation describes only the resulting supported layouts.

## Decision and drift log

| Date | Decision or drift | Reason | Approved by | Affected workstreams |
|---|---|---|---|---|
| — | None | — | — | — |
