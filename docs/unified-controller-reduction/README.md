# Unified controller reduction roadmap

This directory specifies a deletion-led simplification pass over the completed unified-controller
architecture. The previous roadmap successfully converged ownership and fixed the browser
connection/retention failure, but it increased production code and the number of concepts required
to understand the system. This pass treats cognitive load and code volume as first-class product
constraints rather than incidental cleanup.

The reduction must preserve the behavior and safety boundaries that justified the unified
controller. It is not permission to reintroduce duplicate owners, unbounded socket retention,
ambiguous state authority or physical output capability.

## Why this pass exists

Measured from the roadmap base `ef9d22f` through the final no-facade commit `61c0ab4`, the previous
work changed 166 files and added 12,121 lines while deleting 5,219. The net growth was:

| Area | Net change |
|---|---:|
| Backend production (`coordinator/src`) | +2,973 |
| Frontend production (`frontend/src`, excluding tests) | +337 |
| Generated live schema | +1,277 |
| Tests | +1,123 |
| Documentation | +975 |
| Deployment, scripts and other files | +217 |

Generated files, tests and documentation are not all maintenance burden in the same way as runtime
code, but the production increase is real. Four files account for most of the backend growth:
`service.py`, `api/models/live.py`, `api/internal/live.py` and `composition.py`. The reduction pass
starts by measuring the current tree rather than assuming every line in those files is unnecessary.

## Product outcome

A new contributor should be able to trace each common flow without learning avoidable intermediate
types or wrappers:

```text
CAN/timer/HTTP intent -> one controller owner -> effects + current projection
current projection   -> bounded Socket.IO publication -> Zustand -> UI
durable HTTP resource <-> SQLite <-> TanStack Query
```

The final implementation should have:

- One operational-state owner and one live-state transport.
- Fewer production files, types, adapters and handoff objects on common paths.
- One obvious representation for each public payload and each internal fact.
- Direct framework-boundary adaptation instead of parallel domain-shaped model trees.
- Only diagnostics that drive an operator decision, safety behavior or verified acceptance check.
- Tests focused on observable contracts and safety invariants rather than private call graphs.
- A materially smaller production tree, not merely shorter formatting or code moved elsewhere.

## Protected behavior

Reduction may not weaken these outcomes:

- Controller inputs remain ordered through one bounded owner.
- Simulation uses the production codecs, transitions and effect path.
- Default live composition cannot transmit; hardware evidence gates remain unchanged.
- HTTP owns semantic commands and durable resources; Socket.IO owns live state.
- Reconnect sends a complete authoritative snapshot and a new `boot_id` invalidates prior live
  revisions.
- One frontend transport owner survives React remount/navigation without duplicate listeners.
- Engine.IO/client publication is bounded so a stalled peer cannot grow memory or block the
  controller.
- Trace retention is bounded and opt-in.
- Fatal controller results are not acknowledged as successful.
- Readiness, shutdown and failure behavior needed by deployment remain testable and honest.
- The former 5–10 minute development-browser crash must not return.

## Reduction accounting

Phase 1 records the exact current baseline and may refine targets only with a written justification.
The default programme target is:

- At least **1,000 net lines removed from production code** across `coordinator/src` and
  `frontend/src`, excluding tests and generated files.
- Every implementation phase is net-negative in production lines. A phase that must add production
  code must remove more in the same phase or stop for explicit approval.
- At least one handoff layer or independently named representation removed from each common flow
  touched by a phase.
- No increase in public routes, socket events, configuration switches, runtime queues, retained
  stores or lifecycle owners.

Line count is a guardrail, not the sole objective. The following do **not** count as reduction:

- Moving code to another directory, package, generated file or dependency.
- Compressing formatting, combining statements or deleting explanatory names.
- Deleting tests without deleting the production behavior they exclusively covered.
- Replacing explicit local code with a generic framework that has more concepts.
- Hiding complexity behind `Any`, unchecked dictionaries, casts or reflection.
- Removing bounds, failure handling, safety gates or useful operator evidence.

Each phase records both volume and cognitive measures:

| Measure | Meaning |
|---|---|
| Production lines | Added/deleted lines in tracked backend/frontend production files |
| Production files | Files added, deleted and touched |
| Named concepts | Public/private types, wrappers, queues, owners and projections introduced/removed |
| Flow hops | Files and transformations crossed by the phase's common path |
| Contract copies | Independently maintained representations of the same payload/fact |
| Verification surface | Tests retained, deleted as obsolete, or added for externally visible risk |

## Phases

| Phase | Document | Outcome | Minimum production reduction |
|---:|---|---|---:|
| 1 | [Baseline and deletion map](01-baseline-and-deletion-map.md) | Reproducible measurements, flow maps and approved deletion ledger | No production change |
| 2 | [Contract and model consolidation](02-contract-and-model-consolidation.md) | Fewer representations and boundary adapters for live/resource contracts | 200 lines |
| 3 | [Runtime and service reduction](03-runtime-and-service-reduction.md) | Smaller single-owner runtime with fewer handoff objects and wrappers | 300 lines |
| 4 | [Publication and diagnostics reduction](04-publication-and-diagnostics-reduction.md) | Simpler bounded Socket.IO/health path with only decision-useful diagnostics | 300 lines |
| 5 | [Composition and frontend seams](05-composition-and-frontend-seams.md) | Fewer construction/configuration and frontend ownership layers | 200 lines |
| 6 | [Test-suite reduction](06-test-suite-reduction.md) | Smaller behavior-focused suite without implementation archaeology | Net-negative test code |
| 7 | [Integrated cutover and acceptance](07-cutover-and-acceptance.md) | Dead-code removal, target reconciliation and full behavioral acceptance | Overall target met |

Minimums are planning budgets, not permission to make unsafe deletion. A phase may exceed its
budget and reduce a later phase's requirement. If evidence shows a target cannot be met without
weakening protected behavior, record the concrete blocker and request a decision; do not inflate a
diff with cosmetic churn.

## Working method

Give one implementation agent one phase at a time using
[phase-agent-prompt.md](phase-agent-prompt.md). The agent must read the latest
[implementation log](implementation-log.md), measure the phase base before editing and report the
deletion hypothesis before implementation.

Review must ask two separate questions:

1. Does observable behavior and safety still pass?
2. Is the result materially easier to understand and smaller, or did it merely rearrange code?

A phase is not `Verified` until both answers are supported by evidence.

## Global non-goals

- Reopening architecture choices solely to produce a larger deletion count.
- Replacing the single owner with callbacks spread across adapters or request handlers.
- Returning live state to HTTP or durable state to Zustand.
- Removing bounded client queues, reconnect snapshots or boot/revision semantics.
- Removing health/readiness facts required by supervision or fault diagnosis.
- Chasing a coverage percentage or test count at the expense of meaningful behavior coverage.
- Combining unrelated responsibilities into a large file to reduce file count.
- Introducing a dependency-injection framework, event bus, broker or schema platform.
- Enabling or claiming physical CAN/steering behavior.
- Rewriting stable UI or domain behavior that has no measurable simplification payoff.
