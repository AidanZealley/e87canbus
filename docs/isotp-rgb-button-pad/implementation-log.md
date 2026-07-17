# ISO-TP/RGB button-pad implementation log

[Overview](README.md) · [Phase prompt](phase-agent-prompt.md)

This is the append-only record for the two phases. Read it completely before
starting a phase, update the status row and append an entry in the same change,
and do not rewrite prior entries except to correct factual errors.

## Phase status

| Phase | Status | Completed by | Date | Verification |
|---|---|---|---|---|
| 1 | Not started | — | — | — |
| 2 | Not started | — | — | — |

Allowed statuses are Not started, In progress, Completed, and Blocked. A phase
is not complete until every required check in its phase document passed. A
blocked entry must identify the concrete blocker and the repository state.

## Entries

### Entry template

```markdown
### Phase <number> — <title> — <YYYY-MM-DD>

- **Agent:** <identifier or "not available">
- **Final status:** <Completed or Blocked>

#### Summary

<Outcome and intentionally excluded work.>

#### Important files changed

- `<path>` — <reason>

#### Public contract or wire changes

<Exact change, or "None".>

#### Verification

| Command | Result |
|---|---|
| `<exact command>` | <result> |

#### Decisions, deviations, and limitations

- <Decision/deviation/limitation, or "None beyond the phase document".>

#### Follow-up work

- <Specific next phase or hardware-evidence item.>
```
