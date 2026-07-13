# Phase implementation prompt

Copy everything below the line, replace `{N}` with the phase number, and give it to a fresh agent.

---

You are implementing **Phase {N}** of hardening pass 01 in this repo.

Read these first, in order:

1. `docs/hardening-01/README.md` — goals, binding code standards, architecture map, checks.
2. `docs/hardening-01/IMPLEMENTATION_LOG.md` — what previous phases actually did, including any
   deviations from their phase docs.
3. The phase doc for Phase {N} (linked from the README's phase table).

Then implement the phase exactly as specified. Design decisions in the phase doc are already made
— do not re-litigate them. If you hit a genuine contradiction between the phase doc and the code
as it exists now, resolve it in the way that best serves the goals in the README, and record the
deviation and its reasoning in your log entry.

## Non-negotiable code quality requirements

This codebase is read and maintained by a human. Optimize for that above all else:

- **Simplicity first.** The least complex code that does the job. If you find yourself building a
  registry, base class, or new layer the phase doc didn't ask for — stop and use a function or a
  dict instead.
- **Prefer deleting code over adding it.** Prefer deduplicating over abstracting.
- **Plain data:** frozen dataclasses, dicts, tuples, enums. No cleverness.
- **No if/elif chains that dispatch on cases** — use a lookup table with small, well-named
  handler functions.
- **Split logic into small utility functions when it helps a reader**, keep it inline when
  splitting would just create hop-chasing.
- **Every new behaviour gets a test** that reads as arrange / act / assert. Deterministic — use
  the injectable clocks; never `time.sleep` in a test.
- **Match the existing style** of neighbouring code (naming, logging, docstring tone, test
  structure).

## Rules

- Implement **only** Phase {N}. Do not start the next phase, even partially.
- Stay behaviour-preserving except where the phase doc explicitly changes behaviour.
- Do not touch `protocol/custom_ids.md`, `devices/` firmware, or any BMW placeholder IDs unless
  the phase doc says to. Never invent or "verify" a BMW CAN ID.
- Preserve the import direction: nothing in `application/` may import `protocol/`, `runtime`,
  `simulation/`, or `adapters/`.
- Update any README or docs sections the phase invalidates (the phase doc lists the known ones —
  grep to catch stragglers).

## When you are done

1. Run all checks from the repo root and make them pass:
   - `uv run pytest -q`
   - `uv run mypy`
   - `uv run ruff check coordinator`
   - If you touched `frontend/`: `cd frontend && pnpm typecheck && pnpm lint`
2. Append an entry to `docs/hardening-01/IMPLEMENTATION_LOG.md` following the template at the top
   of that file, and flip the phase's row in its status table. Be honest: record deviations,
   anything you found that the phase doc missed, and anything you deliberately left for a later
   phase.
3. Report back with a summary of what changed, the check results, and any deviations.

Do not commit unless asked.
