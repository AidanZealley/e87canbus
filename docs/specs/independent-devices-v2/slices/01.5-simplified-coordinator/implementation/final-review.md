# Simplified coordinator whole-feature review

Status: not started. Begin only after every workstream is accepted.

The final-review lead owns the Final row in [plan.md](plan.md), triages the findings,
sends each accepted correction to a fresh implementation agent, runs focused closure, writes this
record and makes one commit.

## Reviewer task packet

Review the complete branch against the starting commit in [plan.md](plan.md), Slice 1.5, ADR 0018
and the linked product documents. Read accepted handoffs, then independently inspect the cumulative
diff and surrounding code.

Audit complete removal, the fresh-database empty profile seed, retained desired state, vehicle decoding,
single-owner ordering, runtime lifecycle, browser contracts, generated artifacts, dependency
direction, stale mocks and unjustified machinery.

Trace these cases end to end:

- a fresh database contains one selected `Default` profile with sixteen unassigned slots;
- vehicle frames retain network and ingress time, decode once and update the browser projection;
- desired steering, curve and profile changes work without a device registry or actuator;
- browser SSE publishes complete current projections with its one boot-scoped revision source;
- live startup creates no CAN transmitter or output executor; and
- simulation supplies vehicle input without project-device peers or a second state owner.

Search the full repository for the removed command, custom protocol, registry, ISO-TP, old firmware,
`DeviceRole`, `DeviceSource`, device lifecycle and catalogue types, effect execution, applied
Servotronic, lighting topic and project-device simulation controls.

Confirm every retained kernel concern supports vehicle observations, desired intents, profiles and
curves, or complete publication projections. Reject compatibility facades, no-op shells, empty
unions, generic output hooks and configuration retained only for a hypothetical vehicle action.

## Review briefs

Initial whole-feature review:

```text
Act as the whole-feature reviewer for the simplified coordinator workflow. Read docs/specs/independent-devices-v2/slices/01.5-simplified-coordinator/implementation/README.md, plan.md, all four accepted workstream records, Slice 1.5, ADR 0018 and every source linked by the README. Review the complete branch diff against the starting commit and inspect surrounding code. Run proportionate read-only checks. Write findings only in this file's Initial whole-feature review section. Audit removal of high-beam and command-specific defaults; the fresh-database selected empty Default profile; complete removal of button-pad and Servotronic transport and execution; deletion of DeviceRole, DeviceSource, custom protocol, registry, ISO-TP, old firmware, project-device simulation and effect machinery; preservation of desired steering, profiles, curves and vehicle observations; single-owner ordering; runtime lifecycle; browser SSE revisions; generated contracts; dependencies; stale mocks; and unjustified abstractions. Trace the specified end-to-end cases and classify evidence-backed findings as Required, Optional or Question, grouped by original workstream owner.
```

Focused closure review:

```text
Perform the focused whole-feature closure review for the simplified coordinator workflow. Read final-review.md including the Initial whole-feature review and Lead triage, plus affected workstream Resolution records. Inspect the cumulative branch diff against the recorded starting commit. Verify every accepted Required finding and check its correction for release-blocking database seed, ownership, vehicle-decoding, publication, lifecycle or incomplete-deletion defects. Do not reopen optional suggestions or perform another open-ended review. Write the verdict only in this file's Focused closure section. Return a final verdict and any remaining blockers with evidence.
```

## Final verification

Run from the repository root:

```text
uv run pytest -q
uv run mypy
uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py
uv run lint-imports
git diff --check
```

Run from `frontend/`:

```text
pnpm api:check
pnpm typecheck
pnpm lint
pnpm test
pnpm build
```

No hardware or vehicle validation follows this review. This slice removes unverified output and must
not claim a physical actuation result.

## Initial whole-feature review

- Reviewer: Fresh whole-feature review agent.
- Branch, base and reviewed head: `feature/simplified-coordinator`, `d2c00ed5313954142ff8205da5adab4da5882f48`, `20b788b`.
- Verification run: 52 focused SQLite, kernel, loop, live, SSE and simulation tests passed. OpenAPI generation `--check`, frontend `pnpm api:check`, `uv run lint-imports`, and `git diff --check d2c00ed...HEAD` passed. Repository searches covered the retired command, device types, protocol, registry, ISO-TP, firmware, effects, applied output, lighting and simulator peers.
- Acceptance-criteria audit: A fresh database seeds one selected `Default` profile with sixteen empty slots. Simulated vehicle frames cross the in-memory bus and retain network and ingress time before one kernel decode; complete vehicle and engine projections reach SSE. Operator and retained button intents update desired steering, profiles and curves without a registry or actuator. The controller loop remains the bounded owner, owns one boot-scoped revision and per-topic revisions, and publishes complete browser replacements. Live composition creates receive-only CAN readers and no output executor or transmitter. The old device transport, firmware and simulation peers are removed. The findings below concern dead commit data and current descriptions that disagree with this result.
- Required findings by owner:
  1. Workstream 4: `hosts/src/e87canbus/kernel/commit.py:44-49` retains `Commit.snapshot`, but both runtimes discard it when building `RuntimeExecution` (`runners/live.py:265-270`, `runners/simulation/runtime.py:177-187`). The service obtains the complete projection separately through `runtime.projection()` (`service/loop.py:445-466`). Repository search finds no production reader of `commit.snapshot`; only tests read it. This duplicate full projection is a retained kernel value without a consumer. Remove it and keep the service's complete publication snapshot. The same file's `changed_controller_topics(..., health_changed=...)` parameter is always passed `False`; health commits already use `_commit_health`. Remove that dead branch with the commit simplification.
  2. Workstream 1: `frontend/README.md:72-73` still lists a `lighting` projection in the current Zustand store. The generated browser contract, SSE publisher and store have no such projection. Update this current guide to match the removed high-beam feature.
  3. Workstream 3: `frontend/README.md:101-112` still describes `effective assistance` and a marker derived from current speed and controller assistance, although those applied-output calculations and the marker were deleted. `domain/buttons/profiles.py:175-181` also says the pad is running and obeying the active profile, although this slice has no pad input or configuration transport. Describe the values as desired coordinator state and remove the stale marker description.
- Optional observations: None.
- Questions: None.
- Verdict: Changes requested for the three Required findings. The traced runtime, seed, SSE and deletion criteria otherwise match Slice 1.5; no hardware or vehicle behavior was validated.

## Lead triage

- Accepted findings and owners: All three Required findings accepted. Workstream 4 owns removal of unused `Commit.snapshot` and the always-false `health_changed` branch. Workstream 1 owns the stale frontend lighting projection claim. Workstream 3 owns the stale applied-assistance, marker and active-pad claims. One fresh correction agent owns the affected kernel code, direct tests and current documentation.
- Rejected findings and reasons: None.
- Deferred optional observations: None.
- Drift requiring user decision: None. These corrections align the implementation and current documentation with approved Slice 1.5 behavior.

## Correction evidence

- Owner: Whole-feature correction agent for accepted Workstream 1, 3 and 4 findings.
- Correction: Removed the unused full projection from `Commit` and the always-false
  `health_changed` argument. The kernel still reports fixed changed topics; the service continues
  to obtain complete publication state through `runtime.projection()`. Direct kernel tests now read
  the kernel snapshot. Updated the frontend guide to omit lighting, applied assistance and the
  removed active marker, and changed `ActiveButtonProfile` documentation to describe coordinator
  selection rather than pad execution.
- Focused verification: 31 runtime, profile, controller-loop, live and simulation tests passed.
  `uv run mypy`, targeted `uv run ruff check`, and `git diff --check` passed. A reference search
  found no remaining `commit.snapshot` readers or `health_changed` uses.
- Deletion and simplification pass: Removed the duplicate projection value and dead health branch
  directly, without a replacement field, facade or publication path.

## Focused closure

- Reviewed head: `20b788b9be85666a0e51d3955a2e91833265f38f` with the uncommitted correction diff, against starting commit `d2c00ed5313954142ff8205da5adab4da5882f48`.
- Finding outcomes: All three accepted Required findings are resolved. `Commit` now carries only changed topics; the always-false `health_changed` branch and all `commit.snapshot` readers are gone. Live and simulated runtimes still pass those topics to the single-owner controller loop, which reads the complete projection through `runtime.projection()`. `frontend/README.md` no longer claims a lighting projection, effective assistance or an active curve marker. `ActiveButtonProfile` now describes the coordinator's selected profile instead of pad execution.
- Final simplification assessment: The correction removes duplicate commit data and dead comparison logic without adding a facade or second publication path. The cumulative diff still seeds the selected empty `Default` profile, decodes routed vehicle frames in the kernel, and publishes complete browser projections with the loop's revision source. Focused runtime, profile, loop, SSE, SQLite and simulation tests passed (47); mypy, targeted ruff and `git diff --check` passed.
- Remaining blockers: None found in the accepted corrections. No hardware or vehicle validation was performed.
- Verdict: Approved for final verification.

## Completion record

- Final verification: `uv run pytest -q` passed (593 tests); `uv run mypy`, `uv run ruff check e87ctl hosts scripts/watch_frontend_contracts.py`, `uv run lint-imports`, and `git diff --check` passed. From `frontend/`, `pnpm api:check`, `pnpm typecheck`, `pnpm lint`, and `pnpm build` passed. `pnpm test` timed out on one console route test at its 5-second limit; the complete console suite passed with one worker (97 tests), and the coordinator-client (20) and coordinator (36) suites passed. No frontend application code changed in the correction pass.
- External validation pending: None for Slice 1.5.
- Specification drift: None. The three corrections remove unused data and align current descriptions with approved behavior.
