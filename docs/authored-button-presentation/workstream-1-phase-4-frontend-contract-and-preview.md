# Workstream 1, phase 4 — Frontend contract and preview

[Overview](README.md) · [Workstream 1](workstream-1-authored-button-colours.md) ·
[Workstream 2](workstream-2-configuration-screen.md)

**Status:** Not started. Phases 1-3 are complete and committed on branch
`authored-button-colours`. This is the last phase of workstream 1.

This document is written to be handed to a fresh agent or session with no
memory of the preceding work. Read
[workstream-1-authored-button-colours.md](workstream-1-authored-button-colours.md)
and [README.md](README.md) first — they are the authority for the design.

## Outcome

The frontend compiles and behaves correctly against canonical button-profile slots, and
the editor's LED preview mirrors the new visual-state derivation instead of the
deleted colour table.

This phase does **not** redesign the editor. The 4×4 editable pad and the binding
dialog stay exactly as they are; replacing them with a vertical list is
[workstream 2](workstream-2-configuration-screen.md), a separate piece of work.
Phase 4 only makes the existing editor correct again.

## Starting state

On branch `authored-button-colours`, everything below is already done:

- **Phase 1** collapsed the `0x701` effect frame to one generic `blink` opcode
  carrying a pulse count and RGB, and replaced `ButtonFeedbackColour` with
  `ButtonFeedback(rgb, pulses)`.
- **Phase 2** moved slots from bare commands to `ButtonSlot` objects and added
  catalogue activeness predicates.
- **Phase 3** replaced the hardcoded colour table with a four-value
  `ButtonVisual` derivation, made rendering a pure function of
  `(slot values, visual state)`, and deleted `ButtonCommandPresentation`,
  `maximum_assistance_indexes()`, `SOFT_WHITE` and `OFF_BUTTON_LEDS`.

The coordinator is green: `uv run pytest -q`, `uv run mypy`,
`uv run ruff check coordinator scripts/watch_frontend_contracts.py`,
`uv run lint-imports`, `scripts/generate_custom_protocol.py --check` and
`pnpm api:check` all pass, and `pio run` in `devices/button-pad` builds.

**The generated HTTP contract is already current.** `protocol/openapi.json` and
`frontend/src/api/http/*.gen.ts` were regenerated in phase 2 and `pnpm api:check`
passes. Do not expect regeneration to produce changes; if it does, something has
drifted and that is a finding, not a step.

## The problem to fix

`pnpm typecheck` fails with 40 errors across 9 files, all in
`frontend/src/components/button-profile-editor/`. They have a single root cause:
a slot used to be a bare command and is now an object wrapping one.

```
21  utils.ts
 4  utils.test.ts
 4  button-led-presentation.test.ts
 3  ButtonProfileEditor.tsx
 3  ButtonBindingDialog.test.tsx
 2  button-led-presentation.ts
 1  types.ts
 1  ButtonProfileGrid.test.tsx
 1  ButtonProfileEditor.test.tsx
```

Representative:

```
types.ts(33,30):  Property 'type' does not exist on type 'ButtonProfileSlotRequest'.
utils.ts(32,19):  Property 'type' does not exist on type 'ButtonProfileSlotRequest'.
ButtonProfileEditor.tsx(79,5):  Type 'ButtonProfileSlotRequest | null' is not
                                assignable to type 'ButtonProfileSlotResponse | null'.
```

`pnpm lint` additionally fails on `ButtonProfileEditor.tsx(11,1)` — unused `Card`
imports. That failure **predates all of this work** (it reproduces on the base
commit), but this phase owns the file, so fix it here.

## Required changes

### 1. `types.ts` — separate the slot from the command

`ButtonCommandSlots` is currently `ButtonProfileDefinitionRequest["slots"]`, and
`ButtonCommand` is `ButtonCommandSlots[number]`. A slot element is now
`ButtonProfileSlotRequest | null`, so `ButtonCommand` must be derived from the
slot's `command` field rather than from the slot itself. Keep the existing
tuple-length discipline: `toButtonCommandSlots` and `BUTTON_SLOT_COUNT` exist so
a backend pad-size change fails the build here rather than at runtime, and that
property must survive.

### 2. `utils.ts` — operate on commands, not slots

`commandLabel` and the form-value helpers take a command. Thread `slot.command`
through at the call sites. `commandToFormValue`, `formValueToCommand` and
`ButtonCommandFormValue` stay for now — the binding dialog still uses them, and
they are deleted in workstream 2, not here.

### 3. `ButtonProfileEditor.tsx` — build whole slots

`commitBinding` currently writes a bare command into a slot array; it must
construct a complete `ButtonSlot`.

Assigning a command therefore needs a **default colour**, because the editor has
no colour picker until workstream 2 and `colour` is required. Use the same
defaults the coordinator uses so a button assigned in the UI looks like the same
button assigned by the built-in profile:

| Command | Default colour |
| --- | --- |
| `select_steering_mode`, `toggle_automatic_assistance` | `[0, 0, 255]` |
| everything else | `[255, 255, 255]` |

`active_colour` is always `null` and `animation` is always `null` in this phase —
there is no UI to author either. Editing a slot that already carries a colour or
animation must **preserve** it rather than resetting to the default; a user's
authored value must not be destroyed by an unrelated command change. State that
intent in a comment, because nothing in the UI yet reveals the value being
preserved.

Also delete the unused `Card` imports at line 11.

### 4. `button-led-presentation.ts` — mirror the new derivation

This file exists because the editor previews a **draft** profile that is not
active, so no endpoint can derive its colours. It mirrors the coordinator and
carries a "change both together" note; keep that note and keep the constants
pinned by its test.

Replace the seven-command colour switch with the two-stage rule from phase 3:

**Stage 1 — visual state**, mirroring
`coordinator/src/e87canbus/domain/controller/button_leds.py`, in priority order:

1. slot is `null` → `UNASSIGNED`
2. link unsynchronized, or the command requires Servotronic and it is unusable →
   `UNAVAILABLE`
3. the command's activeness predicate holds → `ACTIVE`
4. otherwise → `INACTIVE`

The predicate is parameter-dependent and must be mirrored from the catalogue —
`select_steering_mode(auto)` is active only in automatic,
`set_manual_assistance_level(n)` only at level `n`,
`set_maximum_assistance(enabled)` when maximum-assistance active equals
`enabled`, and `adjust_manual_assistance` / `start_high_beam_strobe` never. Read
`coordinator/src/e87canbus/domain/buttons/catalogue.py` for the authoritative
list, including how `MaximumAssistance` collapses to manual.

**Stage 2 — colour**:

| Visual | Colour |
| --- | --- |
| `UNASSIGNED` | `[0, 0, 0]` |
| `UNAVAILABLE` | `SOFT_AMBER [8, 6, 0]` |
| `ACTIVE` | `active_colour ?? colour`, full brightness |
| `INACTIVE` | `colour` dimmed |

The dim is **nearest-integer rounding**, `(channel * 8 + 127) / 255` floored —
NOT truncation. Truncation yields `(8,5,0)` for amber and cannot reproduce
`SOFT_AMBER`. Match `resting_rgb` in `button_leds.py` exactly.

**Animation is not previewed in this phase.** An `ACTIVE` slot with a breathe or
blink animation previews as its steady full-brightness colour. Animating the
editor preview needs the track renderer and belongs with the animation controls
in workstream 2. Say so in a comment so the omission is visibly deliberate.

### 5. Tests

Update the four failing test modules. Two rules:

- `button-led-presentation.test.ts` must keep **literal** expected values for the
  two pinned constants — `(8,8,8)` from white and `(8,6,0)` from amber. Do not
  compute an expectation with the same dim function under test; that would let a
  bug in it pass silently.
- Add coverage for each visual state, including the parameter-dependent active
  cases and the unavailable-overrides-active case.

## Definition of done

From `frontend/`: `pnpm typecheck`, `pnpm lint`, `pnpm test` and `pnpm build` all
pass. From the repo root, the coordinator gate is untouched and still green — see
`.github/workflows/ci.yml` for exactly what CI runs.

No file outside `frontend/src/components/button-profile-editor/` should need to
change. If something else does, that is worth reporting rather than absorbing.

Do not run `ruff format` over `scripts/` — CI does not format-check it and it
produces unrelated churn.

## Out of scope

- Replacing the pad grid with a vertical list, the colour picker, the animation
  controls, and the command/parameter selects — all
  [workstream 2](workstream-2-configuration-screen.md).
- Any coordinator, protocol or firmware change.
- Animating the editor preview.

## Suggested process

The preceding three phases each ran as an implementation agent followed by an
independent review agent that re-ran the full CI gate itself rather than trusting
the implementer's claims. That caught a latent bypass of a validation bound, a
missing protocol version bump, and a re-export alias — none of which the
implementer had flagged. It is worth repeating here even though this phase is
smaller.
