# Phase Implementation Prompt

Copy everything below the line, replace `{N}` with the phase number, and give it to a fresh agent.

---

You are implementing **Phase {N}** of hardening pass 02 in this repository.

Read these files completely, in order:

1. `docs/hardening-02/README.md` — target architecture, binding invariants, binding code standards,
   phase order, and checks.
2. `docs/hardening-02/IMPLEMENTATION_LOG.md` — the codebase as previous phases actually left it,
   including deviations and discovered constraints.
3. The Phase {N} document linked from the README phase table.

Then inspect the current code and tests in the phase's scope before editing. The phase document's
design decisions are already made; implement that phase only. If the current code genuinely
contradicts the phase specification, resolve it in the way that best preserves the README's safety,
simplicity, same-path simulation, and one-state-owner invariants, then record the deviation.

## Primary quality requirement

Simple, readable, minimal code is a required outcome of this migration. Do not mechanically layer
the new architecture over the old one. Take every reasonable opportunity within the files and
boundaries touched by this phase to remove spaghetti, duplicated paths, excessive verbosity,
unnecessary wrappers, stale compatibility code, and abstractions that no longer earn their keep.

The result should have fewer ways to do the same thing and a more obvious control flow. A phase is
not complete if the new path works but the old path, redundant helpers, or obsolete state plumbing
remain beside it.

## Implementation rules

- **Prefer deletion.** Delete superseded code in this phase. Do not leave commented code, aliases
  "for now", or parallel old/new event pipelines unless the phase explicitly requires a temporary
  adapter—and then delete it by the phase's acceptance gate.
- **Use plain constructs.** Prefer frozen dataclasses, functions, tuples, dicts, enums, and direct
  `match` statements. Do not introduce a registry, base-class hierarchy, manager/factory layer,
  decorator registration, service locator, or generic event bus unless the phase explicitly calls
  for it.
- **Make boundaries do work.** A wrapper or class must enforce a real invariant, own state, or
  isolate I/O. Delete pass-through abstractions that only rename calls.
- **Keep the main path readable.** Input → decode → transition → commit → effect should remain
  traceable by reading a small number of plainly named functions in order.
- **Simplify touched code.** If code in scope has nested conditionals, duplicated branches, dead
  state, unused helpers, verbose plumbing, or misleading names, clean it up while preserving the
  phase boundary and behavior.
- **Do not create unrelated scope.** If a cleanup would require partially implementing a later phase
  or changing an unrelated subsystem, record it in the log rather than leaving a half-migration.
- **Prefer better data shapes to defensive branching.** Encode legal states directly and derive
  projections instead of synchronizing multiple mutable flags.
- **Keep public APIs small.** Add only the entry points required by the phase and remove replaced
  mutation paths before completion.
- **Keep tests behavioral.** Use deterministic clocks, table-driven transitions, and small real
  compositions. Do not use `time.sleep`, deeply mock internal call chains, or lock tests to private
  helper layout.
- **Match neighboring style.** Use `from __future__ import annotations`, frozen dataclasses,
  `StrEnum`, module-level logging, and arrange/act/assert tests where applicable.
- **Comments explain constraints, not narration.** Preserve explanations of safety, ordering,
  overload, and drop behavior; remove comments made obsolete by clearer code.

Do not treat fewer lines as the only goal. Explicit safety code is valuable. However, if the phase
adds a material abstraction or increases production code substantially, be able to state which
duplicated responsibility or failure mode it replaces. If it replaces nothing, reconsider it.

## Safety and architecture rules

- Implement only Phase {N}; do not begin later feature or migration phases.
- Preserve the same-path property: simulated CAN input must use the production decode, transition,
  commit, effect, and TX-policy path.
- Preserve import direction. Domain/application code must not import protocol, runtime, simulation,
  adapters, FastAPI, threading, or queue.
- Never invent, infer, or promote a placeholder BMW ID or payload to executable behavior.
- Default live composition remains unable to transmit unless the phase explicitly operates on the
  later, evidence-gated deployment grant.
- Do not weaken queue bounds, timestamp ownership, TX capability checks, rate limits, or publication
  ordering to preserve an incidental test expectation.
- Update documentation made inaccurate by the phase and grep for stale descriptions.

## Required simplification audit

Before running final checks, review every production file changed in the phase and answer:

1. Is there now exactly one path for each replaced responsibility?
2. Can any compatibility method, wrapper, branch, state field, import, comment, or helper be deleted?
3. Did a new class or module remove more complexity than it introduced?
4. Is the event/control flow visible without dynamic registration or callback chasing?
5. Are invalid states prevented by data shape where practical?
6. Do tests describe behavior rather than implementation structure?

Make the resulting cleanups before declaring the phase complete. Record any deliberate exception in
the implementation log's **Complexity delta** section.

## Completion

1. Run from the repository root:
   - `uv run pytest -q`
   - `uv run mypy`
   - `uv run ruff check coordinator`
   - If the frontend changed: `cd frontend && pnpm typecheck && pnpm lint && pnpm test`
   - If generated protocol artifacts changed: run the generator's `--check` mode.
   - If phase 8 changes actuator firmware: run its documented firmware checks.
2. Verify every acceptance criterion in the phase document.
3. Append a factual entry to `docs/hardening-02/IMPLEMENTATION_LOG.md`, update the status table, and
   include:
   - behavior and boundaries changed;
   - deviations;
   - safety invariants verified;
   - complexity delta and deletions;
   - discoveries and deferred cleanup; and
   - exact check results.
4. Report the outcome, checks, deviations, and any remaining risk.

Do not commit unless explicitly asked.
