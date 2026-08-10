# Workstream 5: Synchronize documentation and architectural records

Status: not started.

## Task packet

### Outcome

Maintained documentation describes the accepted two-host system, final repository paths, separate
frontend and setup commands, fixed Ethernet topology and honest pending hardware validation. Stale
combined coordinator/screen instructions are removed rather than retained as an alternative.

### Scope

- Update the root README and `PROJECT_CONTEXT.md` for `hosts/`, coordinator/console ownership,
  separate frontends and the resulting physical topology.
- Replace the single deployment procedure with clear blank-Pi coordinator and console paths using
  the final scripts, services, frontend artifacts and verification commands from workstream 4.
- Update setup, simulation, reliability, wiring, protocol and other maintained docs containing old
  paths, commands, routes, kiosk ownership or combined-host assumptions.
- Update diagrams and links affected by the split.
- Add a concise ADR recording the accepted separate-host boundary, local receive-only console CAN,
  frontend ownership and constrained point-to-point Ethernet exposure. Reference rather than copy
  existing ADR 0008–0010 reasoning.
- Update the ADR index and clearly retain hardware power/transient validation as separate future
  work.
- Remove stale `coordinator/`, `setup_pi.sh`, combined `frontend/dist`, coordinator kiosk and old
  route instructions from maintained docs.
- Check relative links and commands against the accepted tree.

### Non-goals

- Changing implementation behaviour to make documentation easier.
- Adding aspirational CAN signal features, screen designs or power-protection selection.
- Creating a migration guide for unsupported old combined-role deployment.
- Repeating the full feature specification in every document.
- Claiming physical validation that was not performed.

### Initial ownership

- `README.md`
- `PROJECT_CONTEXT.md`
- `docs/**`, excluding frozen numbered task packets except this workstream's record fields
- `deploy/README.md`
- Documentation comments/examples in configuration files only when they are stale and no behaviour
  changes

Implementation corrections discovered during documentation work return to the orchestrator and
the owning earlier workstream; this agent does not fix production code.

### Required seams

- Use only accepted names, paths, commands, addresses and service ownership recorded by workstreams
  1–4.
- ADR consequences agree with existing single-owner controller, accessory isolation and constrained
  exposure decisions.
- Documentation distinguishes automated/static verification from pending Pi, CAN, Ethernet and
  vehicle-power checks.
- The console activity counter is described only as an end-to-end diagnostic proof, not a decoded
  vehicle feature.

### Acceptance criteria

- A new operator can identify which Pi, HAT, CAN interfaces, frontend, service and setup script
  belong to each host without consulting the feature specification.
- Every maintained setup command and linked repository path exists at the accepted head.
- No maintained document describes the coordinator as owning the driver kiosk or tells users to run
  the removed `setup_pi.sh`.
- README and CI verification commands agree.
- Wiring documents state console K-CAN listen-only, disabled termination and unused second channel
  without claiming unperformed physical validation.
- The new ADR is indexed and does not supersede unrelated decisions.
- Documentation remains concise and links to canonical runbooks rather than duplicating them.

### Targeted verification

```bash
bash -n scripts/*.sh deploy/bin/* deploy/kiosk/*.sh
uv run python scripts/generate_custom_protocol.py --check
uv run pytest -q hosts/tests/test_architecture.py hosts/tests/test_deployment_profiles.py
cd frontend && pnpm install --frozen-lockfile && pnpm api:check && pnpm build
```

Additionally inspect all changed Markdown links and search maintained documentation for
`coordinator/src`, `coordinator/tests`, `setup_pi.sh`, `frontend/dist` and coordinator-owned kiosk
instructions. Any remaining match must describe history or a deliberately retained external fact,
and its reason must be recorded in the handoff.

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
