# Hardening Pass 02 — Event Kernel Migration

This pass migrates the coordinator toward a small control-system kernel: one ordered input stream,
one owner of application state, pure state transitions, and one safety-controlled exit for effects.
It incorporates the remaining findings from hardening pass 01 without replacing the boundaries that
already work.

The migration is deliberately incremental. Every phase leaves the repository runnable, keeps live
and simulated CAN traffic on the same decode/application/effect path, and removes its temporary
compatibility surface before the next phase finishes.

## Outcome

```text
CAN readers ─┐
Timers ──────┼──> bounded, timestamped runtime inbox
Shutdown ────┘                    │
                                  ▼
                         single-owner kernel
                                  │
                         decode domain event
                                  │
                                  ▼
                   transition(state, event, config)
                           │                 │
                       new state          effects
                                               │
                                  safety-controlled executor
                                   ├── CAN transmission
                                   ├── future actuator command
                                   └── committed-state publication
```

The target is an actor/reducer/effect pattern implemented with frozen dataclasses, a bounded queue,
and ordinary functions. This pass must not introduce a global event bus, event sourcing, an Rx
pipeline, a workflow engine, or a dependency-injection framework.

## Binding code standards

Simple, readable, minimal code is a primary deliverable of this migration, not a secondary cleanup.
Every phase must leave the code it touches easier to follow than it found it.

- **Take simplification opportunities in scope.** When a phase exposes duplicated logic, tangled
  control flow, obsolete compatibility code, needless pass-through wrappers, or verbose state
  plumbing in the files it touches, simplify or delete it as part of that phase. Do not preserve
  spaghetti behind a new interface.
- **Prefer deletion and consolidation.** Remove superseded paths in the same phase that replaces
  them. Git history is the archive; commented-out code, indefinite compatibility aliases, and
  parallel old/new pipelines are not acceptable.
- **Use the smallest robust pattern.** Prefer a function, frozen dataclass, tuple, dict, or direct
  `match` over a class hierarchy, registry, manager, factory, plugin mechanism, or callback web.
  Introduce a named abstraction only when it removes more complexity than it adds.
- **Keep control flow visible.** A reader should be able to trace input → transition → commit →
  effect without searching through dynamic registration or multiple indirection layers.
- **Keep APIs narrow.** Minimize public mutation methods and data shapes. Avoid wrappers that merely
  rename or forward every argument without enforcing a real boundary.
- **Split by responsibility, not ceremony.** Extract a helper when its name makes the caller read
  more clearly or isolates a testable rule. Keep short one-use logic inline when extraction would
  create hop-chasing.
- **Make invalid states impossible before adding validation branches.** Prefer better data shapes to
  defensive `if` trees and assertions around contradictory fields.
- **Keep tests readable and behavioral.** Prefer table-driven state/effect examples and real small
  compositions to deep mock graphs or assertions on private helper structure.
- **Comments record constraints.** Do not narrate obvious code. Explain safety limits, ordering
  requirements, and why a tempting alternative is unsafe.
- **Do not optimize for line count alone.** A small amount of explicit code is better than a clever
  abstraction, but every material net increase must be justified by a new required invariant.

Opportunistic cleanup stays within the phase's touched boundaries and must not become an unrelated
rewrite. If a worthwhile simplification requires changing a later phase's boundary, record it in the
implementation log rather than partially building that later phase.

## Binding invariants

1. **Safe live defaults.** Running `uv run e87canbus` with the repository defaults must transmit no
   CAN frames. Bench and simulator TX grants are explicit composition choices.
2. **Observation time is captured at ingress.** Safety decisions never substitute queue-dequeue or
   processing time for the time a frame was received.
3. **One state owner.** Only the kernel commits application state. API handlers, timer tasks, reader
   threads, and simulator devices submit inputs; they do not mutate application state directly.
4. **Legal states are representable; illegal combinations are not.** Steering mode and maximum
   assistance use a tagged state rather than booleans plus hidden saved state.
5. **State transitions are deterministic.** A transition consumes state plus one domain event
   (including its explicit observation time where relevant) and returns new state plus effects. It
   performs no I/O and reads no ambient clock.
6. **Effects have one exit.** CAN authorization and rate policy are applied at the last writable
   boundary. RX-only networks have no transmitter capability in the executor.
7. **Overload is explicit.** Runtime queues are bounded. Overflow and reader failure are visible and
   fail closed; growing latency is not an overload strategy.
8. **Publication follows commit order.** Application snapshots carry a monotonically increasing
   revision. Trace events remain a separate append-only stream.
9. **Simulation remains honest.** Browser actions operate simulated external nodes, which emit real
   frames. No simulator-only API injects domain events or state into the coordinator.
10. **No unverified vehicle behavior.** Real steering decoding or actuation cannot begin until the
    speed message and actuator boundary are verified and documented. Simulator-only definitions
    must remain impossible to compose live.

## Phases

| # | Document | Result | Depends on |
|---|---|---|---|
| 1 | [Immediate live-safety containment](phase-1-immediate-safety.md) | Default live execution is RX-only; SocketCAN faults are isolated; rate-limit semantics are honest | — |
| 2 | [Timestamped, bounded ingress](phase-2-timestamped-ingress.md) | Frames carry observation time and live backlog is bounded | 1 |
| 3 | [Explicit immutable domain state](phase-3-domain-state.md) | Steering and speed state have one source of truth and no invalid combinations | 2 |
| 4 | [Pure transitions and controlled effects](phase-4-transitions-and-effects.md) | Application decisions are pure and all writes pass through capability-based safety policy | 3 |
| 5 | [Single-owner kernel and live cutover](phase-5-kernel-and-live.md) | Startup, frames, timers, faults, and shutdown use one ordered kernel input path | 4 |
| 6 | [Simulator and API cutover](phase-6-simulator-and-api.md) | Simulation uses the same kernel; publications are ordered and revisioned | 5 |
| 7 | [Protocol source of truth and cleanup](phase-7-protocol-and-cleanup.md) | Protocol artifacts cannot drift and migration scaffolding/dead state is gone | 6 |
| 8 | [Steering failsafe groundwork](phase-8-steering-failsafe.md) | Simulator proves stale-speed, overload, fault, shutdown, recovery, and watchdog paths; real actuation remains blocked | 7; verified captures/hardware still gate road use |
| 9 | [Correctness and safety truth](phase-9-correctness-and-safety-truth.md) | Physical claims match available evidence; time, failures, fatal health, and revisions are internally consistent | 8 |
| 10 | [Simulation semantics and observability](phase-10-simulation-semantics-and-observability.md) | Vehicle speed and controller projections have honest semantics and are visible in the workbench | 9 |
| 11 | [Operational hardening and closeout](phase-11-operational-hardening-and-closeout.md) | Publication and cleanup are bounded; simulation-only boundaries and final simplicity are verified | 10 |

Phases 1–7 are architecture work that can be completed with the current verified protocol. Phase 8
was reduced to explicitly synthetic, simulator-only groundwork because external evidence is not
available. It does not add a BMW ID, current value, actuator adapter, or live grant; those parts
remain gated and must not be simulated into existence.

Phases 9–11 close findings from the post-Phase-8 review. They correct evidence and event-system
invariants, make the reduced simulation honest and observable, and finish bounded operational
hardening. They do not relax any physical evidence gate or extend the live steering scope.

## Post-Phase-8 follow-ups

| Review finding | Addressed in |
|---|---|
| Authoritative context still contains unsupported current, hardware, and control claims | Phase 9 |
| Timer time can regress and a fatal simulator output fault does not stop the session | Phase 9 |
| Optional network fields implicitly distinguish CAN from actuator failures | Phase 9 |
| `SetVehicleSpeed` emits once rather than setting external simulated-vehicle state | Phase 10 |
| Fallback reasons and steering-controller projection are ambiguous or absent from the UI | Phase 10 |
| First-command and shutdown-originated actuator failures can escape simulator publication | Phase 11 |
| A non-failing slow WebSocket can block the simulation owner indefinitely | Phase 11 |
| Tick configuration and per-interface SocketCAN cleanup lack complete validation/isolation | Phase 11 |
| Reactive simulated CAN devices will require bounded quiescence processing | Phase 11 gate; implement with the first reactive device |

## Carried findings

| Finding still relevant after hardening 01 | Addressed in |
|---|---|
| Default live K-CAN TX sends unvalidated `0x701` startup frames | Phase 1 |
| `python-can` send/receive errors escape current isolation | Phase 1, then fault inputs in phase 5 |
| Queue-dequeue time can make an old speed frame appear fresh | Phase 2 |
| Live ingress queue is unbounded | Phase 2 |
| Steering state and speed validity have multiple mutable sources of truth | Phase 3 |
| TX policy is outside the state/effect model and the per-ID field is misleading | Phase 4 |
| Reader death, timers, startup, and frames do not share one ordered input path | Phase 5 |
| Tick broadcasts can repeat command state and concurrent publications can reorder | Phase 6 |
| Firmware, Python, and Markdown protocol definitions can still drift | Phase 7 |
| Speed staleness is a flag, not yet a safe actuator command | Phase 8 |

## Migration discipline

- Implement one phase per commit and append its result to `IMPLEMENTATION_LOG.md`.
- Use [PROMPT.md](PROMPT.md) for every implementation phase; its simplicity review is mandatory.
- Read the previous phase's log entry before starting the next phase.
- Compatibility adapters may exist only within the phase that introduces their replacement. Each
  phase's acceptance criteria name the old entry points that must be deleted before completion.
- Prefer characterization tests before changing behavior. Tests should assert observable contracts,
  not private helper layout.
- Do not combine feature work with phases 1–7. Phase 8 is the first feature-bearing phase.
- Keep the application/runtime single-threaded. Threading and queue primitives belong in the live
  composition only.
- Finish each phase with a simplification audit of every production file touched: remove dead imports,
  obsolete helpers, duplicated branches, unnecessary wrappers, and stale comments before declaring
  the phase complete.

## Checks

Every phase must finish with:

```bash
uv run pytest -q
uv run mypy
uv run ruff check coordinator
```

Phases touching the frontend must also run:

```bash
cd frontend
pnpm typecheck
pnpm lint
pnpm test
```

Phases changing generated protocol artifacts must run the generator's `--check` mode. Any phase
that changes actuator firmware must also run its documented firmware checks; phases 8–11 must not
claim those checks apply while the verified hardware boundary remains absent.
