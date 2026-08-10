# Coordinator and console split whole-feature review

Status: not started. Begin only after every numbered workstream is accepted.

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

- Reviewer: `TBD`
- Branch, base, and reviewed head: `TBD`
- Verification run: `TBD`
- Acceptance-criteria audit: `TBD`
- Required findings by owner: `TBD`
- Optional observations: `TBD`
- Questions: `TBD`
- Verdict: `TBD`

## Orchestrator triage

- Accepted findings and owners: `TBD`
- Rejected findings and reasons: `TBD`
- Deferred optional observations: `TBD`
- Drift requiring user decision: `TBD`

Return each accepted correction to its original implementation owner in one consolidated batch.
Each owner records the correction in its numbered Resolution section. Do not create a new generic
cleanup workstream or allow owners to redesign frozen seams silently.

## Focused closure

The same final reviewer checks accepted findings, their fixes and release-blocking regressions
introduced by those fixes. It does not restart broad review or promote optional observations.

- Reviewed head: `TBD`
- Finding outcomes: `TBD`
- Final simplification assessment: `TBD`
- Remaining blockers: `TBD`
- Verdict: `TBD`

## Orchestrator completion record

- Final head and verification: `TBD`
- External validation pending: `TBD`
- Specification drift: `TBD`
- Completion report delivered: `TBD`

