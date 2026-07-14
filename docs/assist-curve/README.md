# Steering assistance curve roadmap

This directory breaks the assistance-curve editor and profile storage into independently
implementable phases. The first usable release keeps interpolation in the coordinator. The profile
model and activation boundary deliberately allow a future steering controller to become the
runtime consumer without changing the editor or saved-profile format.

The proposed long-term ownership decision is recorded separately in
[ADR 0007](../decisions/0007-steering-controller-owns-assistance-mapping.md). It is not a prerequisite
for these phases and does not authorize physical steering output.

Before starting a phase, use the reusable [phase agent prompt](phase-agent-prompt.md) and review the
[implementation log](implementation-log.md). The implementing agent should append a concise entry
to the log when it finishes or encounters a material blocker.

## Product model

The feature exposes three deliberately different states:

| State | Owner | Lifetime | Meaning |
|---|---|---|---|
| Draft | Browser | Until navigation/revert | Values currently being edited |
| Active | Coordinator activation boundary | Until replacement/restart | Definition currently used by the runtime consumer |
| Saved | SQLite on the coordinator host | Across restarts | Named, revisioned profile |

An active definition may be unsaved. A saved profile may be inactive. The UI must never use the
word `saved` to imply `active`, or `active` to imply that a future physical controller has
acknowledged it.

Version 1 has eight fixed speed points at `0, 10, 20, 30, 60, 100, 160, and 250 km/h`. The editor
changes assistance vertically only. This is an editor/profile contract rather than a verified
vehicle-speed or steering-hardware fact.

## Phase order

| Phase | Document | Deliverable | Depends on |
|---:|---|---|---|
| 1 | [Profile domain model](01-profile-domain-model.md) | Versioned, validated curve/profile values | None |
| 2 | [SQLite persistence](02-sqlite-persistence.md) | Durable named profiles and optimistic revisions | Phase 1 |
| 3 | [Runtime activation](03-runtime-activation.md) | Ordered hot-swap of the active definition | Phase 1 |
| 4 | [Profile API](04-profile-api.md) | CRUD, activation and publication contracts | Phases 1–3 |
| 5 | [Interactive editor](05-interactive-editor.md) | Touch-friendly draggable Recharts editor | Phase 4 |
| 6 | [Smooth interpolation](06-smooth-interpolation.md) | Versioned monotone interpolation shared across implementations | Phases 1–5 |

Phases 2 and 3 can be implemented in parallel after Phase 1. Phase 4 joins them. Phase 5 should
initially render the existing linear interpolation honestly. Phase 6 changes the curve algorithm
only after storage, activation and editing are stable.

## Cross-phase invariants

- The frontend never reads or writes SQLite directly.
- Every boundary validates finite values, point count, speed ordering, assistance bounds, schema
  version and interpolation version.
- Editing pointer movement changes only browser draft state. Network and disk writes occur on
  explicit actions.
- Saved-profile updates use optimistic concurrency; stale clients cannot silently overwrite newer
  revisions.
- Runtime activation passes through the single-owner coordinator path. An API task must not mutate
  a curve behind the kernel.
- The graph represents the actual interpolation algorithm. A visually smoothed line must not hide
  a linear runtime calculation.
- Profile configuration carries no live-CAN or physical-actuator authority.
- Units and serialization are deterministic so the same profile can later be transferred to an
  embedded controller.

## Engineering constraints

Maintainability is a primary product requirement for every phase:

- Implement only the current phase and the smallest prerequisites it genuinely needs. Do not add
  speculative controller transport, generalized configuration frameworks or future-facing service
  layers.
- Preserve the established boundaries between pure domain/application decisions, persistence and
  I/O adapters, runtime composition, API orchestration, simulation, protocol code and frontend
  components.
- Prefer plain immutable values and small named functions over inheritance, registries, dependency
  injection frameworks or generic abstractions. Introduce an interface only where there are real
  owners/implementations to separate or where a test boundary materially benefits.
- Keep the main behavior readable from a small number of files. Avoid pass-through wrappers and
  types that merely rename another type without enforcing a domain rule.
- Follow the existing directory and naming conventions. New frontend components must follow
  `frontend/AGENTS.md`.
- Comments should explain decisions, invariants, units and non-obvious failure behavior. Do not add
  comments that merely restate straightforward code.
- Update the nearest README or design document when a public contract, startup behavior, operator
  workflow or module responsibility changes.
- Add focused tests at the boundary that owns each rule. Do not compensate for unclear production
  code with excessive mocking or a parallel test-only architecture.
- Adding a dependency requires a concrete reduction in code or risk and should be called out in the
  implementation log.

If a phase cannot be implemented cleanly without violating these constraints, stop and record the
design pressure rather than adding another layer to hide it.

## Definition of the first usable release

The first usable release is complete after Phase 5 when a user can:

1. Open the workbench and see the active curve.
2. Drag fixed-speed control points vertically with mouse or touch.
3. Revert the draft without affecting runtime behavior.
4. Apply a validated draft to the coordinator simulator.
5. Save it as a named revisioned profile.
6. Reload the page or coordinator and retrieve saved profiles.
7. Clearly see whether draft, active and saved values differ.

The first release remains simulation-only. Smooth interpolation, controller synchronization and
physical output are separate changes.
