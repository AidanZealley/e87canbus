# Simulated independent button pad whole-feature review

Status: accepted.

The final-review lead owns the Final row in [plan.md](plan.md), triages the findings, sends each
accepted correction to a fresh implementation agent, runs focused closure, writes this record and
makes one commit.

## Reviewer task packet

Review the full branch against the starting commit recorded in [plan.md](plan.md) and the approved
Slice 02 sources. Read accepted handoffs, but independently inspect the combined diff and surrounding
code.

Audit specification completeness, preservation of the accepted Slice 1.5 boundary and vehicle CAN,
certificate identity and authorization, scene semantics, retained desired steering
state, migration safety, generation durability, status receipt, canonical press dispatch, initial
SSE ordering, bounded consumers, lifespan teardown, nginx and generated contracts, simulation
composition, dependency direction, stale mocks and meaningful tests.

Trace these cases end to end rather than accepting layer-local tests:

- a fresh simulated identity starts, authenticates, receives and validates the current scene, then
  reports the applied generation;
- a profile or application-state change that changes the steady scene advances and publishes once;
- reconnect and coordinator restart preserve generation;
- a simulated tap crosses HTTP once and reaches the active profile's intent once;
- press feedback does not become a configuration document;
- desired steering state still changes without claiming an applied hardware value; and
- repository-wide searches confirm the workflow did not reintroduce the generated custom protocol,
  coordinator-device ISO-TP, device registry/lifecycle, legacy project-device firmware or a
  project-device CAN simulation path.

Confirm the result uses direct role-specific code for the one implemented device. Reject a role
plugin system, event log, shared generic SSE framework, replay protocol, presence tracking, auth
bypass, transport-neutral payload store or configuration point without an approved requirement.

## Review briefs

Initial whole-feature review:

```text
Act as the whole-feature reviewer for the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/README.md, plan.md, all six accepted workstream records, docs/specs/independent-devices-v2/slices/02-simulated-button-pad.md, architecture-and-boundaries.md, live-and-device-api.md, first-device-delivery.md, the accepted Slice 1.5 handoff and the ADRs linked by the README. Review the complete branch diff against the starting commit recorded in the plan and inspect surrounding code. Run proportionate read-only checks. Write findings only in this file's Initial whole-feature review section. Audit that the accepted coordinator-device CAN, generated custom protocol, ISO-TP, registry/lifecycle, legacy firmware and project-device simulator removals remain intact; preservation of vehicle CAN and desired steering state; certificate identity and closed authorization; exact feedback-free scene semantics; SQLite migration and generations; status receipt; canonical direct button input; initial SSE ordering; bounded consumers; lifecycle; nginx; OpenAPI and generated artifacts; production-path simulation; dependency direction; stale mocks and unjustified machinery. Return a verdict followed by evidence-backed Required findings grouped by original workstream owner, Optional observations and Questions.
```

Focused closure review:

```text
Perform the focused whole-feature closure review for the simulated independent button-pad workflow. Read docs/specs/independent-devices-v2/slices/02-simulated-button-pad/implementation/final-review.md, including the Initial whole-feature review and Lead triage, plus the affected workstream Resolution records. Inspect the cumulative branch diff against the starting commit. Verify every accepted Required finding and check those corrections for release-blocking defects and unnecessary compatibility or generic machinery. Do not reopen optional suggestions or perform another open-ended review. Write the verdict only in this file's Focused closure section. Return a final verdict and any remaining blockers with evidence.
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

No external validation gate follows this review. Hardware, real nginx mutual TLS, Wi-Fi, device
flash and physical CAN belong to later slices and must not be claimed here.

## Initial whole-feature review

- Reviewer: Fresh whole-feature review agent.
- Branch, base and reviewed head: `feature/simulated-button-pad`, `64183cd0c68a3d2fa7a94ae978873495d6926270`, `6e852dbdd4668877fdb38a2d232d052811e50caa`.
- Verification run: 44 focused scene, runtime, repository, device API, configuration stream and simulator tests passed. `uv run mypy`, `uv run ruff check hosts`, `uv run lint-imports`, OpenAPI generation `--check`, frontend `pnpm api:check` and `git diff --check 64183cd..HEAD` passed. A direct kernel check reproduced the finding below. These are proportionate review checks; the final repository suite remains the lead's completion gate.
- Acceptance-criteria audit: The cumulative diff adds a strict 16-button, brightness-255 scene with resolved colours and active-only animations, and no press-feedback field. Certificate SAN parsing yields canonical device IDs and closed roles; the permission table and route dependency keep the button-pad routes closed to console, operator, unknown-role and Servotronic principals. SQLite migration 10 adds direct configuration and last-status tables; transactions serialize first creation and changed-document generation writes, while status stores a coordinator UTC receipt time. Configuration registration and its initial durable envelope share a lock with publication; output uses complete SSE records, idle comments, bounded pending state and request cleanup. The simulator's private authenticated ASGI client applies validated envelopes, reports status and posts each tap once through the production press handler and controller inbox. Nginx forwards certificate metadata and disables buffering for the device stream; OpenAPI and generated Hey API artifacts match. Vehicle CAN decoding and desired steering state remain. Source searches found no restored coordinator-device CAN path, generated custom protocol, ISO-TP, registry, legacy project-device firmware or project-device CAN simulator. The application-state publication gap below prevents full acceptance.
- Required findings by owner:
  1. Workstream 5, with the kernel topic comparison it integrated: `hosts/src/e87canbus/kernel/commit.py:73-83` emits `BUTTONS` only when the active profile ID or saved revision changes. It does not compare the new `ApplicationSnapshot.button_pad` projection. `hosts/src/e87canbus/api/internal/device_configuration.py:62-65` offers a snapshot only for `BUTTONS`, so a steering intent that changes a button's active condition never advances SQLite generation or publishes the replacement. I started a kernel with button 5 bound to `ToggleAutomaticAssistance`, then dispatched that intent. The resolved colour changed from `(12, 34, 56)` to `(0, 1, 2)`, while `changed_topics` was only `{STEERING}`. The existing runtime test at `hosts/tests/test_button_profile_runtime.py:73` asserts that incomplete topic set. Update topic detection for changes to the resolved button scene and cover a state-only transition through the durable stream and status path. This is required by Slice 02's immediate application-state scene updates.
- Optional observations: The development tap route is installed for a `FULL` simulation API even when `create_app(simulate_button_pad=False)` or an injected authenticator leaves `app.state.simulated_button_pad` empty. In those test compositions, the route raises instead of returning its declared 503 (`hosts/src/e87canbus/runners/simulation/api/routes/button_pad.py:24-25`). The normal simulator creates the client, so this does not block Slice 02.
- Questions: None.
- Verdict: Changes required for the missing application-state scene publication. The remaining traced paths and focused checks passed; hardware, real nginx mutual TLS, Wi-Fi, flash and physical CAN were outside this review.

## Lead triage

- Accepted findings and owners: The Workstream 5 publication finding is Required. `BUTTONS`
  currently tracks only profile identity and revision, while a steering transition changes the
  resolved scene. A correction agent owns the kernel topic comparison, focused runtime and durable
  stream tests, and the Workstream 5 Resolution note. The final repository suite also found a
  Workstream 6 architecture violation: shared API lifecycle imports the simulation client solely
  for an annotation. A fresh correction agent owns removing that dependency and recording it in
  Workstream 6's Resolution.
- Rejected findings and reasons: None.
- Deferred optional observations: The disabled-simulator development tap route can raise instead
  of returning its declared 503 in test-only app compositions. The normal simulator starts its
  client; this does not affect the delivered device path.
- Drift requiring user decision: None.

## Correction evidence

- Workstream 5 correction agent: `changed_controller_topics` now includes a change to the resolved
  `button_pad` projection in `BUTTONS`. The runtime topic assertion was updated. A production-path
  simulator test changes steering state without changing profile identity or revision, then checks
  the new scene, stored generation 2 and received status generation 2. The affected Workstream 5
  Resolution records the correction. Twenty focused tests, mypy, focused Ruff and
  `git diff --check` passed. The agent found no additional machinery to remove.
- Workstream 6 correction agent: Removed the simulation-client import and annotation from the
  shared API lifecycle; its startup and shutdown calls are unchanged. The affected Workstream 6
  Resolution records the correction. Twenty-eight architecture, lifecycle, simulator and stream
  tests passed, along with mypy, focused Ruff and `git diff --check`.

## Focused closure

- Reviewed head: `6e852dbdd4668877fdb38a2d232d052811e50caa` plus the uncommitted
  Workstream 5 and 6 corrections, against starting commit
  `64183cd0c68a3d2fa7a94ae978873495d6926270`. This supersedes the earlier focused closure.
- Finding outcomes: Both accepted corrections are closed. `changed_controller_topics()` compares
  the resolved `button_pad` projection, so a steering-only change emits `BUTTONS`. The
  production-path simulator test keeps profile identity and revision constant, then verifies the
  changed colour reaches the pad, SQLite stores generation 2 and device status reports generation
  2. The shared lifecycle module no longer imports the simulation client. `api/main.py` still
  creates that client for simulator composition, and the lifecycle still starts it after the
  configuration publisher and stops it before the publisher and controller.
- Final simplification assessment: The fixes add one projection comparison, remove one import and
  annotation, and extend existing tests. They add no compatibility path, generic machinery or
  second generation source.
- Verification: 51 focused runtime, configuration, simulator, lifecycle, route and authorization
  tests passed. Targeted mypy and Ruff, import contracts and `git diff --check` against the starting
  commit passed. The lead still owns final repository verification.
- Remaining blockers: None found.
- Verdict: Accepted for focused closure.

## Completion record

- Final verification: `uv run pytest -q` passed, 645 tests. Mypy, Ruff, import contracts,
  `git diff --check`, frontend `pnpm api:check`, `pnpm typecheck`, `pnpm lint` and `pnpm build`
  passed. The default `pnpm test` run hit five-second console route test timeouts. The client
  passed 20 tests in that run; console passed 97 and coordinator passed 36 with one Vitest worker
  each. The console route file also passed alone, 5 tests.
- External validation pending: None for Slice 02.
- Specification drift: None.
