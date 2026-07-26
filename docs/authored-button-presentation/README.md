# Authored button presentation

**Status:** Design settled, not started. Two independent workstreams.

Today a button's LED colour is derived entirely from which command occupies the
slot: `derived_button_led_state` maps a `ButtonCommandPresentation` category to
a hardcoded colour. A user can choose what a button *does* but not what it
*looks like*. This folder covers giving the colour to the user, and rebuilding
the configuration screen that has to express it.

- [Workstream 1 — Authored button colours](workstream-1-authored-button-colours.md)
  extends the profile slot with a colour and an optional animation, and replaces
  the derived colour table with a rendering rule over authored values.
- [Workstream 2 — Button configuration screen](workstream-2-configuration-screen.md)
  replaces the editable 4×4 pad with a vertical list whose items can hold
  per-command parameters and presentation controls.

The two are separable. Workstream 2's tidy-up (removing the forked pad grid and
the binding dialog) does not depend on workstream 1; workstream 2's presentation
controls do.

## Settled design

### One authored colour per slot

Each assigned button carries a single base colour. It renders:

- **faint** when the button's condition is inactive, or when the command has no
  condition at all;
- **full brightness** when the condition is active.

The faint value is the base colour scaled by 8/255. That factor is not arbitrary:
`SOFT_WHITE (8,8,8)` is `RGB_WHITE × 8/255` and `SOFT_AMBER (8,6,0)` is
`RGB_AMBER × 8/255`, so the existing constants are already this rule with the
base hardcoded. The built-in profile and newly assigned commands use matching
defaults, except where noted below.

### Accepted regression

`select_steering_mode` and `toggle_automatic_assistance` are currently `BLUE` at
full brightness in automatic and `AMBER` at full brightness in manual — bright in
both states. Under a single base colour they become faint-blue in manual and
full-blue in automatic. Manual mode therefore reads as a nearly unlit button,
which is harder to distinguish at a glance from an unassigned one.

This is accepted for the first implementation. The stored shape reserves
`active_colour` so restoring a distinct second colour later is a UI change and a
default rather than a cross-layer stored-shape change.

### Activeness is a property of the bound command, not the command type

The second brightness applies to any command with an observable condition, which
is a larger set than "toggles":

| Command | Active when |
| --- | --- |
| `select_steering_mode(mode)` | current mode is `mode` |
| `toggle_automatic_assistance` | current mode is automatic |
| `set_maximum_assistance(enabled)` | maximum-assistance active equals `enabled` |
| `toggle_maximum_assistance` | maximum assistance is active |
| `set_manual_assistance_level(level)` | current manual level is `level` |
| `adjust_manual_assistance(delta)` | never — no condition |
| `start_high_beam_strobe` | never — see open questions |

Three of those are setters rather than toggles. Scoping the bright state to
toggles alone would take `select_steering_mode`, `set_maximum_assistance` and
`set_manual_assistance_level` dark, which is a visible regression on the pad
that ships today.

Because `select_steering_mode(mode=auto)` is active and
`select_steering_mode(mode=manual)` is not, the predicate reads the bound
command's parameters, not just its type.

### Commands stay structured

Commands keep their `type` plus typed parameters. Flattening the catalogue into
one option per concrete binding was considered and rejected: it forecloses
commands carrying free numeric input or a wide enum, which are wanted.

### System colours stay system colours

Three treatments remain uniform across the pad and are not authorable, because
their value is that they read identically on every button:

- **unavailable** — the persistent `SOFT_AMBER` resting override applied when the
  link is unsynchronized or Servotronic is unusable;
- **rejected press** — `RED` double blink (configuration rejects the command);
- **unavailable press** — `AMBER` double blink.

They are system *values*, not a system *mechanism*: they travel over the same
generic RGB-carrying effect command as the authored acknowledgement flash, rather
than over dedicated per-colour opcodes. See workstream 1, "Press feedback".

## Non-goals

- Per-state colour authoring beyond the single base colour (the field is
  reserved, the UI is not built).
- Authoring the unavailable or fault treatments.
- Brightness/dim-factor configuration; 8/255 is a constant.
- Gradients, per-LED effects beyond the existing solid/blink/breathe track kinds,
  or any new device-side effect.
- Multiple stored profiles, profile switching UI, or import/export.
- Physical NeoTrellis current limiting or brightness calibration.

## Open questions

1. **Amber base collides with the unavailable indication.** An amber base at rest
   is `(8,6,0)`, pixel-identical to `SOFT_AMBER`. Options: reserve amber in the
   picker, use a different dim factor for unavailable, or give unavailable a
   non-static treatment (slow pulse) so it is distinguished by behaviour. The
   last is preferred and is specified as optional in workstream 1.
2. **`start_high_beam_strobe` has a duration but no active state.** It could
   reasonably light while the strobe runs. Deferred; it needs a strobe-running
   flag the LED derivation can read.
3. **Whether the acknowledgement flash should be distinguishable from a rejected
   press when the authored base colour is red.** Both become a red flash on the
   same button, separated only by pulse count (1 versus 2). Probably acceptable;
   revisit if it reads ambiguously on the bench.
