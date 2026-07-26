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

**Collapsed item** — a single row: the preview button, the command name, the
authored colour as a swatch, and expand/clear actions.

**Expanded item** — adds the command select, the parameter control for the
selected command, the colour picker, and the animation control.

Above the list, an optional 4×4 pad navigator: the same simulated pad, where
tapping a button scrolls to and expands the matching item. This keeps the spatial
map — sixteen stacked cards otherwise make "which one is top-left" non-obvious —
without giving the pad any editing responsibility. Build the list first; the
navigator is additive.

## Item contents

**Preview button.** The shared `NeoTrellisButton`, identical in appearance to the
simulated pad, fed the same authored preview colours the pad shows. It is
press-enabled only when the button pad is emulated: `tapSimulationButton` is a
simulator route and `SimulatorNeoTrellis` already gates it on
`source_mode === "emulated"` and `status === "active"`. With real pad hardware
attached the preview renders identically but is not interactive. Do not add a
hardware press-injection endpoint in this workstream.

**Command select.** Grouped by the catalogue, one option per command type.
Commands are not flattened into one option per concrete binding.

**Parameter control.** Driven by the selected command's catalogue fields — an
enum select for `Literal` fields, a number input for bounded integers, nothing
for parameterless commands. Derive it from the generated command models rather
than a hand-written switch, so a new catalogue entry needs no editor change.

**Colour picker.** One picker, the base colour. Needs a luminance floor: at 8/255
anything dark is indistinguishable from unassigned. Constrain the picker rather
than validating after the fact. Show both renderings — faint and full — since one
authored value produces both.

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

`ButtonProfileGrid` is not a variant of the simulated pad button — it is a fork
of it, with a different radius, a dashed unassigned state, an inline label, and
its own colour styling instead of `ledStyle` and the LED CSS variables. It has
drifted and will keep drifting.

1. Move `NeoTrellisButton` out of `components/simulator-workbench/` to a shared
   location and have both the simulator pad and this screen consume it unchanged.
   It already takes no editor-specific props.
2. Delete `ButtonProfileGrid.tsx`, `ButtonProfilePad.tsx`,
   `ButtonBindingDialog.tsx` and their tests.
3. Delete `commandToFormValue`, `formValueToCommand` and
   `ButtonCommandFormValue` if the new parameter controls are derived from the
   catalogue rather than from a flat form value. Keep `commandLabel`.
4. Fix the mangled indentation in `components/car-buttons/CarButtons.tsx` and
   update its "Click a button to change its command" copy.

Steps 1, 2 and 4 do not depend on workstream 1.

## Responsive behaviour

The list is single-column at every width; items reflow internally rather than
scrolling horizontally. No part of the screen may require horizontal scroll at
narrow widths — that failure is the reason for the workstream.

## Accessibility

- Expand/collapse uses `aria-expanded` and `aria-controls` on the trigger.
- The preview button keeps a label identifying the button index and its binding.
- The colour picker is operable by keyboard and exposes a text entry for the
  value; a swatch grid alone is not sufficient.
- Colour is never the only carrier of state — the item shows the command name and
  its active/inactive state as text.

## Required tests

- Changing a command saves the expected definition with the correct
  `expected_revision`, and a conflict surfaces through the existing error detail.
- Selecting a command with parameters renders its control; selecting a
  parameterless one renders none.
- The animation control appears only for commands with an active predicate.
- Clear resets a slot to unassigned and the preview renders `RGB_OFF`.
- The preview button is non-interactive when the pad source mode is not
  `emulated`, and dispatches a tap when it is.
- The shared `NeoTrellisButton` renders identically in the simulator pad and the
  configuration list for the same RGB input.

## Acceptance criteria

- No editable 4×4 grid, no binding dialog, and no fork of the pad button remain.
- Every command in the catalogue is fully configurable from the list, including
  its parameters.
- The screen is usable at narrow widths with no horizontal scroll.
- Adding a catalogue command requires no change to the editor's parameter
  rendering.
