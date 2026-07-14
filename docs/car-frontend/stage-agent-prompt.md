# Prompt for an agent starting a car-frontend phase

Copy the prompt below into a new agent session and replace the bracketed values. Give an agent one
phase at a time. If only a slice is wanted, name that slice and explicitly leave all other phase
completion criteria out of scope.

```text
Work on Phase [N — NAME] of the routed development workbench and car-frontend roadmap in this
repository.

Primary phase document:
docs/car-frontend/[PHASE-DOCUMENT].md

Before changing code, read completely:
- PROJECT_CONTEXT.md
- any AGENTS.md applying to files you may change
- docs/car-frontend/README.md
- the primary phase document above
- docs/car-frontend/implementation-log.md
- docs/decisions/0001-single-owner-event-kernel.md
- docs/decisions/0003-production-path-simulation.md
- docs/decisions/0006-evidence-gated-hardware-behavior.md
- docs/decisions/0007-steering-controller-owns-assistance-mapping.md when steering or controller
  state is in scope
- docs/assist-curve/README.md and the directly relevant assist-curve phase documents when steering
  profiles, activation or chart editing are in scope
- frontend/AGENTS.md for every frontend phase
- any additional ADR, module README or API contract directly relevant to this phase

Implement this phase only. Inspect current code and tests before designing changes: the phase
document specifies required behavior, not permission to overwrite newer architecture. If the
implementation log or repository has moved beyond the written plan, reconcile the difference and
explain it before proceeding.

Preserve these project boundaries:
- Pure domain/application behavior stays independent of FastAPI, SQLite and React.
- Runtime mutation remains ordered through the existing bounded single-owner path.
- Synthetic engine messages remain unmistakably simulation-only and must never enter the live
  ProtocolRouter as guessed BMW definitions.
- SQLite transactions do not span runtime commands or WebSocket broadcasts.
- Missing/stale telemetry remains explicit and must never be presented as a convincing zero.
- Draft, saved and active steering curve state remain distinct.
- Simulator device-health states do not prove real heartbeat or diagnostic criteria.
- No phase grants physical steering output authority, real CAN decoding or kiosk deployment.

The key engineering goal is simple, maintainable, well-organized code that a human can follow.
Keep important behavior obvious and local. Respect current boundaries between domain/application
logic, runtime ownership, persistence/I/O adapters, API orchestration, simulation, protocol code,
query/cache state and frontend components.

In particular:
- Prefer direct immutable data and small named functions over generic frameworks.
- Add an interface only for a real ownership boundary or useful test seam.
- Do not introduce speculative service layers, registries, factories or future hardware
  abstractions.
- Avoid pass-through wrappers and excessive file fragmentation.
- Follow frontend/AGENTS.md component organization and use existing shadcn primitives before
  creating controls.
- Use existing shadcn design tokens or named Tailwind colors; do not add raw page-specific colors.
- Optimize the car UI for 800x480 landscape, but do not impose a fixed minimum control size or add
  pixel-size assertions. Record physical touch tuning as later manual work.
- Keep comments focused on invariants, units, ownership and failure behavior.
- Add focused tests at the layer that owns each rule.
- Update relevant README/API/schema documentation when behavior changes.
- Preserve unrelated user worktree changes.
- Do not implement later phases unless a tiny prerequisite is unavoidable; record it explicitly.

Before implementing:
1. Summarize the intended phase outcome and non-goals.
2. Identify expected files and shared composition points.
3. Inspect git status and call out existing changes you must preserve.
4. State the focused and repository-level verification you expect to run.

Then implement, test and review the diff for unnecessary abstraction, scope creep, false hardware
claims, invented data states and frontend overflow.

At the end:
1. Check every completion criterion in the primary phase document and state which are satisfied.
2. Append a factual entry to docs/car-frontend/implementation-log.md using its template and update
   the phase status table.
3. Report changed files, public-contract or migration impact, exact verification, visual checks,
   remaining work and deviations from the phase specification.
4. Do not mark the phase Verified unless every completion criterion and relevant repository-wide
   check passes. UI phases also require the specified browser matrix; physical-display tuning may
   remain explicitly outstanding where the roadmap says it is manual follow-up.

If a clean implementation conflicts with the phase specification or current architecture, stop at
the smallest safe point, record the pressure clearly and request a decision rather than concealing
the mismatch behind another abstraction.
```

## Phase document values

| Phase | Name | Document |
|---:|---|---|
| 1 | Routing and layouts | `01-routing-and-layouts.md` |
| 2 | Application settings | `02-application-settings.md` |
| 3 | Engine telemetry simulation | `03-engine-telemetry-simulation.md` |
| 4 | Device health | `04-device-health.md` |
| 5 | Car UI foundation | `05-car-ui-foundation.md` |
| 6 | Car screens | `06-car-screens.md` |
| 7 | Verification and acceptance | `07-verification-and-acceptance.md` |

## Optional phase-specific context

Add only information that changes implementation choices, for example:

- A deliberately smaller slice than the full phase.
- An approved change to a public JSON or settings contract.
- Which agent owns a shared composition file during parallel work.
- Existing worktree changes that must be preserved.
- A failed check, migration state or browser limitation from the latest log entry.
- Whether earlier phases are present on the current branch or must be treated as prerequisites.

Do not paste the whole roadmap into the prompt. The agent is required to read the source documents.

