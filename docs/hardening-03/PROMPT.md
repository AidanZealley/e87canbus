# Phase Implementation Prompt

Copy everything below the line, replace `{N}` with the phase number, and give it to a fresh agent.

---

You are implementing **Phase {N}** of hardening pass 03 in this repository.

Read these files completely, in order:

1. `docs/hardening-03/README.md` — target architecture, binding design, invariants, phase order, and
   checks.
2. `docs/hardening-03/IMPLEMENTATION_LOG.md` — results and constraints from earlier phases.
3. The Phase {N} document linked from the README phase table.

Then inspect every current production and test boundary named by the phase before editing. The phase
document's design decisions are already made. Implement that phase only and record any necessary
deviation.

## Primary quality requirement

Leave exactly one obvious LED-state path. Prefer deletion, frozen values, tuples, functions, and
direct codecs. Do not layer a snapshot system over retained indexed mutation APIs, add a generic
event bus, introduce a manager/factory hierarchy, or preserve dual DLC-2/DLC-8 production decoding.

## Safety and scope rules

- Preserve input → decode → transition → commit → effect → policy ordering.
- Simulated button-pad behavior must use the production effect, encoder, CAN frame, decoder, and
  device-state path.
- Application/domain code must not import protocol, runtime, simulation, adapters, FastAPI,
  threading, or queue.
- Default live composition remains unable to transmit.
- Do not promote provisional `0x700`/`0x701` IDs to validated in-car behavior.
- A malformed snapshot changes no LED; do not partially apply valid prefixes.
- Do not queue dropped LED snapshots or replay stale intermediate states.
- Do not invent NeoTrellis hardware topology, mapping, brightness, or current limits.
- Update documentation made inaccurate by the phase and grep for stale indexed-update descriptions.

## Required simplification audit

Before final checks, review every changed production file:

1. Is there one complete LED state, one effect, one encoder, one decoder, and one publication shape?
2. Can any indexed update type, helper, branch, event, compatibility codec, or stale constant be
   deleted?
3. Does every added wrapper enforce exact length, atomic validation, I/O isolation, or another real
   invariant?
4. Can the complete path be followed without registration or callback chasing?
5. Do tests assert state replacement and malformed-frame behavior rather than private layout?

Make those cleanups before completion and record any exception in the complexity delta.

## Completion

Run from the repository root:

```bash
uv run pytest -q
uv run mypy
uv run ruff check coordinator
cd frontend && pnpm typecheck && pnpm lint && pnpm test
```

If generated artifacts changed, run the protocol generator's `--check` mode. If firmware changed,
run `cd devices/button-pad && pio run`.

Verify every phase acceptance criterion, update the hardening-03 status table, and append a factual
log entry covering behavior, deviations, safety invariants, complexity/deletions, discoveries, and
exact checks. Do not commit unless explicitly asked.
