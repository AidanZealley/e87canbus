# Workstream 2 — Button configuration screen

[Overview](README.md) · [Workstream 1](workstream-1-authored-button-colours.md)

**Status:** Not started. The tidy-up section can land independently; the
presentation controls require workstream 1.

## Outcome

`/car/buttons` becomes a vertical list of per-button items rather than an
editable 4×4 pad driving a modal. Each item owns its own layout, so it can carry
whatever parameter controls its command needs and, once workstream 1 lands, a
colour and animation.

## Why not the pad, and why not a table

The editable pad puts sixteen bindings in sixteen small squares. A square holds a
truncated two-line label and nothing else, which is why editing had to happen in
a dialog, and it is unusable at small widths.

A table was considered and rejected. A table's contract is that every row has the
same cells, and this data does not: commands carry different parameters (an enum
select, a free number, or nothing), and only commands with an active condition
can carry an animation. Expressing that in a table means inert cells and
`colSpan` detail rows, which is working around the abstraction rather than using
it. A list of items with bespoke internal layout has no such constraint, and
gives working expand/collapse animation (which a `<td>` does not reliably
support) and a natural stacked form on narrow screens.

## Shape

A vertical list of sixteen items, one per button index.

**Collapsed item** — a single row: a clear button number, the command name, the
authored colour as a paired-swatch popover trigger, and expand/clear actions. The
button number is part of the item design, not a small simulated pad button.

**Expanded item** — adds the command select, the parameter control for the
selected command, and the animation control. Colour editing stays in the
popover available from the row rather than consuming expanded-item space.

There is no pad preview or 4×4 pad navigator on this screen. The visible button
number is the item's spatial reference; the simulated pad and its interaction
remain on the simulation screen.

## Item contents

**Button number.** A prominent, non-interactive number identifying the physical
button index. It must remain easy to scan in both collapsed and expanded states
and must not resemble or behave like a simulated pad button. Pad interaction and
`NeoTrellisButton` remain exclusive to the simulation screen.

**Command select.** Grouped by the catalogue, one option per command type.
Commands are not flattened into one option per concrete binding.

**Parameter control.** Driven by the selected command's catalogue fields — an
enum select for `Literal` fields, a number input for bounded integers, nothing
for parameterless commands. Derive it from the generated command models rather
than a hand-written switch, so a new catalogue entry needs no editor change.

**Colour picker.** The compact row control is a button containing two adjacent
swatches: the full authored colour and its derived faint/inactive colour. It is a
popover trigger, not a simulated pad button. Its accessible name includes the
full and faint hex values.

The popover contains a native `<input type="color">`, an exact `#RRGGBB` text
input, and a small set of useful presets. Do not build or add a dependency for a
custom hue/saturation picker in this workstream. Keep a local draft while the
native picker is being dragged; commit a valid native-picker change, confirmed
or blurred hex value, or preset selection rather than sending a mutation for
every intermediate drag event.

The faint swatch uses the same nearest-integer `colour × 8/255` derivation as the
pad. A colour is invalid when that derivation produces `[0, 0, 0]`, because it
would be indistinguishable from unassigned while inactive. Do not save an
invalid draft; keep the popover open and explain the constraint inline so the
user can choose a brighter colour.

**Animation control.** Only shown when the selected command has an active
predicate, since animation applies to the active state. Off / breathe / blink,
with the bounded parameters from workstream 1.

**Clear.** Resets the slot to unassigned.

## Saving

Keep the existing behaviour: each change commits immediately through
`updateButtonProfileMutation` with `expected_revision`, and the query cache is
updated from the response. Do not introduce a dirty-state form over sixteen
slots — the optimistic-concurrency contract is per-save, and batching would mean
one revision conflict discarding unrelated edits.

## Tidy-up

`ButtonProfileGrid` is a configuration-screen variant of the simulated pad
button, with a different radius, a dashed unassigned state, an inline label, and
its own colour styling. The new item design replaces it completely; do not carry
the variant forward or replace it with another small pad-button preview.

1. Keep `NeoTrellisButton` in `components/simulator-workbench/` and use it only
   for simulation. The configuration screen does not consume it.
2. Delete `ButtonProfileGrid.tsx`, `ButtonProfilePad.tsx`,
   `ButtonBindingDialog.tsx` and their tests.
3. Delete `commandToFormValue`, `formValueToCommand` and
   `ButtonCommandFormValue` if the new parameter controls are derived from the
   catalogue rather than from a flat form value. Keep `commandLabel`.
4. Fix the mangled indentation in `components/car-buttons/CarButtons.tsx` and
   update its "Click a button to change its command" copy.

Deleting the old grid, pad, dialog, and their tests, and completing the copy and
indentation tidy-up, do not depend on workstream 1.

## Responsive behaviour

The list is single-column at every width; items reflow internally rather than
scrolling horizontally. No part of the screen may require horizontal scroll at
narrow widths — that failure is the reason for the workstream.

## Accessibility

- Expand/collapse uses `aria-expanded` and `aria-controls` on the trigger.
- Each item's button number is exposed as part of the item's accessible name,
  together with its binding.
- The paired-swatch trigger is keyboard operable, has a visible focus state, and
  announces both the full and faint hex values.
- The popover returns focus to its trigger when closed. Its native picker,
  presets, and exact hex text entry are all keyboard operable; swatches alone
  are not sufficient.
- Colour is never the only carrier of state — the item shows the command name and
  its active/inactive state as text.

## Required tests

- Changing a command saves the expected definition with the correct
  `expected_revision`, and a conflict surfaces through the existing error detail.
- Selecting a command with parameters renders its control; selecting a
  parameterless one renders none.
- The animation control appears only for commands with an active predicate.
- Clear resets a slot to unassigned and the item reflects its unassigned state.
- Every collapsed and expanded item shows the correct button number.
- Configuration items do not render `NeoTrellisButton` or dispatch simulated
  button taps.
- The colour trigger shows the correct full and faint swatches and exposes both
  values in its accessible name.
- Native-picker, hex, and preset changes save valid colours; a colour whose faint
  value is `[0, 0, 0]` remains an unsaved draft with an inline explanation.

## Acceptance criteria

- No editable 4×4 grid, binding dialog, configuration-screen pad-button variant,
  or small button preview remains.
- Every item clearly identifies its button number without relying on the
  simulated pad.
- Colour editing uses a paired-swatch popover trigger and native browser colour
  input; no custom colour-picker dependency or inline row fields are introduced.
- Every command in the catalogue is fully configurable from the list, including
  its parameters.
- The screen is usable at narrow widths with no horizontal scroll.
- Adding a catalogue command requires no change to the editor's parameter
  rendering.
