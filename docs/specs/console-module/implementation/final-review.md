# Coordinator and console split whole-feature review

Status: accepted; whole-feature review and focused closure complete.

## Reviewer task packet

Use a fresh reviewer who did not implement or independently review a numbered stream. Review the
complete integration branch against the starting commit recorded in [plan.md](plan.md) and the
[approved specification](../../console-module.md). Read accepted handoffs, but independently inspect
the assembled diff and surrounding code.

Audit:

- Specification completeness and the explicit complexity constraints
- `hosts/` ownership, import direction and absence of compatibility paths
- Frontend app separation, generated-contract ownership and absence of speculative shared UI
- Console SocketCAN lifecycle, receive-only capability, bounded state/publication and exact local
  contract
- Coordinator control isolation, unchanged failure policy and absence of console dependency
- Two live frontend sources without duplicated authority or queued command replay
- Setup idempotence, exact service sets, targeted frontend builds, fixed origins and loopback binds
- Ethernet subnet/interface exposure, no routing and preserved hotspot isolation
- Console listen-only CAN setup and inactive second controller
- Lifecycle and shutdown behaviour across reader, ASGI, Socket.IO and kiosk services
- Meaningful tests relative to risk, stale mocks/generated artifacts and unnecessary machinery
- Documentation agreement with final code and honest pending hardware validation
- Final simplification: dead combined routes, scripts, units, aliases and docs are deleted

Run the normal repository checks below. Add focused checks only when evidence suggests a specific
risk; do not turn review into an exhaustive permutation exercise.

```bash
uv sync --locked
uv run python scripts/generate_custom_protocol.py --check
uv run pytest -q
uv run mypy
uv run ruff check hosts scripts
uv run lint-imports
bash -n scripts/*.sh deploy/bin/* deploy/kiosk/*.sh
cd frontend
pnpm install --frozen-lockfile
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

Physical blank-Pi installation, direct Ethernet, HAT+ mapping, live K-CAN listen-only observation,
kiosk/touch behaviour, Pi-plus-screen current demand and automotive power behaviour remain pending
unless named evidence was actually produced during implementation.

## Initial whole-feature review

- Reviewer: Codex (`/root/final_reviewer`), fresh whole-feature reviewer with no numbered-stream
  implementation or review role.
- Branch, base, and reviewed head: `feature/coordinator-console-split`, base
  `ec0ae8db772f7f1ef84edd0e3059f02d06dcb6e5`, head
  `57853e80fb362cf837b56dc4a400a7e33c0c0b62`.
- Verification run: `uv` is unavailable, so the locked `.venv` and `PYTHONPATH=hosts/src`
  equivalents were used. The custom-protocol drift check, 845 Python tests, strict mypy over 130
  source files, Ruff and both import-linter contracts passed. Shell parsing passed for
  `scripts/*.sh`, `deploy/bin/*` and `deploy/kiosk/*.sh`. `pnpm install --frozen-lockfile`, every
  constituent coordinator HTTP/live and console-live contract drift check, aggregate typecheck,
  ESLint, 204 frontend tests and both application builds passed. `git diff --check` passed.
  `systemd-analyze verify` accepted the deployment units and reported only the expected missing
  target-host executables (`cage` and the `/opt/e87canbus` entry points) in this development
  checkout. A focused TanStack Query check demonstrated the failure-policy risk below: a default
  mutation invoked while offline remained `pending`/`isPaused` without calling its operation, then
  executed automatically when online state returned.
- Acceptance-criteria audit: The role-neutral `hosts/` move has no compatibility import path; the
  coordinator remains independent, loopback-bound and unchanged in control/failure ownership; and
  the two ordinary Vite apps consume one UI-free generated coordinator client without cross-app
  routes or shared UI machinery. The console backend owns one receive-side K-CAN composition,
  bounded latest-state publication, exact generated version-1 snapshot, prompt fault state and
  orderly reader/ASGI/Socket.IO shutdown; raw CAN content is absent from its contract. Static
  deployment evidence confirms role-targeted builds and service sets, loopback application binds,
  exact origins and interface-bound proxies, the non-routing `10.43.0.0/30` policy, preserved
  hotspot isolation, kernel listen-only `spi1.1` K-CAN and no configured `spi1.2` channel. Obsolete
  combined routes, installer, kiosk, proxy, udev and host-project paths are deleted. Maintained
  documentation and ADR 0011 otherwise agree with the implementation and honestly leave blank-Pi,
  Ethernet, HAT mapping, physical listen-only CAN, kiosk/touch, current-demand and automotive-power
  validation pending. The console coordinator-control failure policy does not pass for the reason
  below.
- Required findings by owner:
  - Workstream 2 (`309fa33987f81fd5c029c6cb087911befb84705a`): coordinator-backed console
    controls are neither consistently unavailable on Ethernet/coordinator loss nor protected from
    later replay. `CarSettings` decides availability only from a previously successful settings
    query, and `ButtonProfileEditor` disables edits only while its mutation is pending; neither
    gates writes on the coordinator live store's synchronized connection. More directly,
    `use-settings-commit.ts` maintains an unbounded promise chain explicitly described as a queue,
    so edits accepted while an earlier request is pending execute later. All generated mutations
    also inherit TanStack Query's default `networkMode: "online"`; the focused check confirmed that
    an offline mutation is paused and automatically executed on reconnection. This violates the
    approved requirements that coordinator-backed controls become unavailable when Ethernet is
    lost, commands are never queued for replay, and console queues remain bounded. Make the console
    reject writes while coordinator state is unsynchronized, ensure already submitted mutations
    fail rather than pause/replay across an offline transition, remove or bound the settings
    promise queue without losing revision-safe behavior, and add focused tests for disconnect,
    attempted write and reconnection with zero delayed coordinator calls.
- Optional observations: Four comments in the duplicated coordinator/console button-profile
  presentation files still name the removed `coordinator/src/...` path. Updating them to `hosts/`
  would keep source guidance synchronized, but this does not affect runtime acceptance.
- Questions: None.
- Verdict: Changes required. The host split, local CAN proof, deployment boundary and documentation
  otherwise satisfy the approved feature, but coordinator commands can currently remain available
  and replay after a console-link outage.

## Orchestrator triage

- Accepted findings and owners: Workstream 2 owner will make coordinator-backed console writes
  unavailable while live state is unsynchronized, prevent TanStack mutations from pausing/replaying
  across offline transitions, remove the unbounded settings promise chain while preserving
  revision-safe writes, and add focused disconnect/write/reconnect tests proving zero delayed
  coordinator calls. The four stale `coordinator/src` source comments are promoted from Optional
  into the same correction batch because the approved simplification boundary explicitly requires
  obsolete paths and comments to be synchronized.
- Rejected findings and reasons: None.
- Deferred optional observations: None.
- Drift requiring user decision: None. The corrections enforce already approved failure and
  simplification requirements without changing product behavior or architecture.

Return each accepted correction to its original implementation owner in one consolidated batch.
Each owner records the correction in its numbered Resolution section. Do not create a new generic
cleanup workstream or allow owners to redesign frozen seams silently.

## Focused closure

The same final reviewer checks accepted findings, their fixes and release-blocking regressions
introduced by those fixes. It does not restart broad review or promote optional observations.

- Reviewed head: `57853e80fb362cf837b56dc4a400a7e33c0c0b62` plus the uncommitted Workstream 2
  whole-feature correction recorded in `02-frontend-workspace-split.md`. The correction diff is
  limited to console write gating/query policy and focused tests, the four accepted comment path
  updates, and workflow records.
- Finding outcomes: Resolved. Settings and button-profile controls now disable from the coordinator
  live store's synchronized state, and both write owners independently reject an attempted commit
  at that boundary. The production console's single `QueryClient` gives every mutation
  `networkMode: "always"` with retries disabled, so an offline operation is attempted once and
  cannot enter TanStack's paused-replay path. Focused tests disconnect each write owner, attempt a
  write, restore a current snapshot and prove zero delayed coordinator calls; the QueryClient test
  independently proves one failed offline call and no call on reconnect. Settings retain revision
  safety by allowing one keyed mutation at a time and deriving each admitted request from the
  latest cached revision. A direct QueryClient check also confirmed the keyed mutation is counted
  synchronously, closing the same-tick admission window. All four promoted stale comments now use
  `hosts/src`.
- Final simplification assessment: Pass. The unbounded settings promise chain and its retained
  closures are deleted. The replacement reuses synchronized live state, one existing TanStack
  mutation key/state check and one small console-owned QueryClient options value; it adds no queue,
  retry wrapper, connectivity facade, compatibility path or cross-application policy. Focused
  verification passed 7 write-safety/query-policy tests, all 101 console tests, console typecheck
  and production build, the 9 affected coordinator presentation tests, aggregate ESLint and
  `git diff --check`.
- Remaining blockers: None.
- Verdict: Pass. Every orchestrator-accepted finding is closed without a release-blocking
  regression introduced by the correction.

## Orchestrator completion record

- Final head and verification: Accepted implementation head
  `9351861dacecf5d53351cc61c08266fcf47092c1`. Final verification passed the custom protocol,
  OpenAPI, HTTP, coordinator-live and console-live drift checks; 845 Python tests; strict mypy over
  130 source files; Ruff; both import-linter contracts; shell parsing; frozen pnpm install;
  aggregate frontend typecheck and ESLint; 208 frontend tests (18 coordinator-client, 101 console,
  89 coordinator); and both production builds. `uv` is unavailable in this environment, so every
  underlying Python check ran from the locked `.venv` with `PYTHONPATH=hosts/src`; the literal
  `uv`-based aggregate wrappers remain unexecuted here. `systemd-analyze verify` found only the
  expected development-host absence of target-Pi executables (`cage` and the `/opt/e87canbus`
  entry points).
- External validation pending: Blank-Pi runs for both roles; HAT+ overlay and `spi1.1` mapping;
  physical kernel listen-only K-CAN observation and inactive `spi1.2`; direct-Ethernet addressing,
  isolation and constrained proxy reachability; kiosk/touch startup; K-CAN transceiver,
  termination, branch wiring and grounding; combined Pi 4/screen peak-current capacity; and
  automotive reverse-battery, cranking, load-dump and vehicle-power behaviour.
- Specification drift: None.
- Completion report delivered: Prepared for the orchestrator's final response on `2026-08-10`.
