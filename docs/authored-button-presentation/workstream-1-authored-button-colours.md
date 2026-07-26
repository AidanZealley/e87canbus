# Workstream 1 — Authored button colours

[Overview](README.md) · [Workstream 2](workstream-2-configuration-screen.md)

**Status:** Not started.

## Outcome

A button profile slot stores what the button does *and* what it looks like. The
derived colour table in `derived_button_led_state` is replaced by a rendering
rule over authored values, and the canonical profile shape gains a colour, a reserved
active colour, and an optional animation.

## Stored shape

`ButtonProfileDefinition.slots` currently holds `ButtonCommand | None`. It
becomes `ButtonSlot | None`:

```json
{
  "command": { "type": "select_steering_mode", "mode": "auto" },
  "colour": [0, 0, 255],
  "active_colour": null,
  "animation": null
}
```

- `colour` — required RGB triple, the base colour.
- `active_colour` — reserved, always `null` in this workstream. `null` means
  "`colour` at full brightness". Storing it now means adding per-state colours
  later touches the editor and a default rather than every persistence and
  transport boundary.
- `animation` — `null` for static, otherwise a tagged object:

```json
{ "kind": "breathe", "period_ms": 2000, "minimum": 8, "maximum": 255 }
{ "kind": "blink", "on_ms": 400, "off_ms": 400 }
```

There is one canonical definition shape: `{ "slots": [...] }`. Button profile
definitions do not carry a `schema_version`, and the SQLite adapter has no
legacy decoder or shape-upgrade path. The fingerprint covers the complete
canonical definition, including presentation — two profiles that look different
are different profiles.

### Animation bounds

Bounds come from `ButtonPadTrackPayload.__post_init__` and must be enforced at
the API boundary rather than only at track construction:

- breathe: `250 <= period_ms <= 10_000`, `0 <= minimum <= maximum <= 255`
  (both pack into `parameter_b` as `minimum | (maximum << 8)`);
- blink: `1 <= on_ms <= 10_000`, `1 <= off_ms <= 10_000`.

`repeat` is `0` (indefinite) for authored animations. Authored animation applies
to the **active** state only; the inactive state is always static faint. A slot
whose command has no active condition may not carry an animation, and the API
rejects one.

Newly assigned commands use blue for steering-mode selection and automatic
assistance, and white for the remaining command types. `active_colour` and
`animation` default to `null`. The built-in profile
(`built_in_button_profile_definition`) uses the same canonical shape directly.

## Activeness in the catalogue

`ButtonCommandSpec` gains an optional predicate:

```python
active: Callable[[ApplicationState, ButtonCommand], bool] | None = None
```

`None` means the command has no observable condition. The predicate takes the
bound command so parameter-dependent activeness (`select_steering_mode(mode)`,
`set_manual_assistance_level(level)`) is expressible. Populate it per the table
in the [overview](README.md).

Implementations must handle `MaximumAssistance` being a distinct steering state
rather than a mode value — `derived_button_led_state` already does this via
`mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode`,
and the predicates need the same treatment.

`ButtonCommandPresentation` loses its role in colour selection and is deleted
outright; see "What this removes" below.

## Rendering rule

Replacing `derived_button_led_state`, per button, highest priority first:

1. **Unassigned** → `RGB_OFF`, static.
2. **Unavailable** → `SOFT_AMBER`, static. Applies when the link is
   unsynchronized, or when the command requires Servotronic and it is unusable.
   Optionally a slow breathe instead of a static colour, which resolves the amber
   collision in the overview's open questions.
3. **Active** (predicate present and true) → `active_colour ?? colour` at full
   brightness, animated if `animation` is set.
4. **Otherwise** → `colour × 8 / 255`, static.

Transient feedback blinks continue to be layered on top by
`ButtonLedProjection.effect`, and take priority while running.

Integer scaling uses nearest-integer rounding — `(channel * 8 + 127) // 255` —
so `RGB_WHITE` yields exactly `(8,8,8)` and `RGB_AMBER` exactly `(8,6,0)`,
matching today's constants. Pin both with a test.

Truncation does not work and must not be used: `191 * 8 // 255` is `5`, so
`RGB_AMBER` would dim to `(8,5,0)` and `SOFT_AMBER` could not be reproduced.
Only the white constant survives truncation, which is why the discrepancy is
easy to miss.

## `ButtonLedState` holds visual states, not colours

Once a button can breathe in its active state, the steady program is no longer
expressible as 16 colours, so `ButtonLedState(tuple[Rgb, ...])` cannot survive
unchanged. Rather than widening it to 16 tracks, narrow it to 16 **visual
states**:

```python
class ButtonVisual(Enum):
    UNASSIGNED = "unassigned"
    UNAVAILABLE = "unavailable"
    ACTIVE = "active"
    INACTIVE = "inactive"
```

These four cases are exactly the rendering rule above, so the enum is complete by
construction and `mypy` exhaustiveness covers every branch that consumes it. The
authored values are fixed for the lifetime of a profile, so:

```
rendered track = f(slot presentation values, visual state)
```

`led_state()` returns the semantic half; `effect()` applies `f` and then overlays
feedback blinks. The type is not on the live contract — the live contract
publishes `buttons.program` — so this change is confined to the domain and its
tests.

The current type holds rendered pixels only because the colour was hardcoded and
there was no other name for the state. Authoring the colour gives the
intermediate value a real one.

### What this removes

The visible-change check at
`coordinator/src/e87canbus/domain/controller/intents.py:112-121` collapses from
two hand-specialised comparisons to one whole-vector comparison: if the visual
states are equal, nothing on the pad changed and the press gets an
acknowledgement flash. Comparing rendered output is never necessary, and
animation phase cannot enter a comparison because it is not in the compared
value.

That deletes, in the same change:

- `ButtonLedProjection.maximum_assistance_indexes()`, whose only purpose was
  asking whether the maximum indicator moved. Its docstring's intent — catch the
  indicator "wherever (and however often) the active profile happens to show it"
  — is what a whole-vector comparison means directly.
- `ButtonCommandPresentation`: the enum, the `presentation` field on
  `ButtonCommandSpec` and its constructor validation, the argument in all seven
  catalogue entries, and `button_command_presentation()` in
  `domain/buttons/commands.py`. Those are its only uses, so once colour is
  authored and `maximum_assistance_indexes` is gone the category is dead. It must
  not be left behind as a vestigial classification.
- The RGB range validation in `ButtonLedState.__post_init__`; enum members are
  valid by construction.
- `OFF_BUTTON_LEDS` (`domain/events.py:53`), which is already unreferenced today.

### Accepted behaviour change

Comparing the whole vector means a press that changes *any* button's appearance
suppresses the acknowledgement flash, where today only the pressed button and the
maximum-assistance indicators are considered. This matters under the new system
because activeness propagates: pressing `adjust_manual_assistance` can flip a
`set_manual_assistance_level(n)` button between active and inactive elsewhere on
the pad, which is real feedback and should not also produce a "nothing happened"
flash.

### No protocol or firmware work

`BUTTON_PAD_TRACK_BREATHE` and `BUTTON_PAD_TRACK_BLINK` already exist in
`protocol/can.py`, `breathe_track` and `blink_track` already exist in
`domain/buttons/pad.py`, the firmware implements breathe in
`embedded-libs/button_pad_effects`, and the browser renderer already decodes all
three kinds in `button-pad-renderer.ts`. The capability is plumbed end to end and
has simply never been authored.

## Press feedback

`ButtonCommandFailed(..., ButtonFeedbackColour.WHITE)` is raised in two places
that mean different things:

- `kernel.py:459` — the button has no binding.
- `intents.py:125` — the press was accepted but changed nothing visible.

The second is the acknowledgement flash and should become a single flash of the
slot's base colour at full brightness. The first has no base colour to flash and
stays `WHITE`.

### The effect frame carries RGB

`adapters/output.py:263-271` currently maps `ButtonFeedbackColour` onto three
colour-specific opcodes in a frame that carries no colour. All feedback — system
flashes included — moves to one generic blink command carrying RGB and a pulse
count. The frame does not need widening: `protocol/custom.toml:39-53` reserves
bytes 5-7 as zero, and `enabled` (byte 4) is only meaningful for breathe, so the
payload fits DLC-8 exactly:

| Byte | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | version | opcode | button index | sequence | pulses | red | green | blue |

`blink_red_double (0x01)`, `blink_white_single (0x03)` and
`blink_amber_double (0x04)` collapse into one `blink` opcode. The firmware needs
no new rendering code: `triggerSingleBlink(index, r, g, b)` and
`triggerDoubleBlink(index, r, g, b)` already exist in
`embedded-libs/button_pad_effects`; dispatch on the pulse count and retire
`triggerRedDoubleBlink`. Pulse count is validated as 1 or 2 at the boundary,
matching the firmware entry points; generalising to N later needs no frame
change.

### `breathe (0x02)` is retired

`SetButtonPadBreathe` is constructed nowhere in `coordinator/src` — only in
`test_output.py` — and its docstring states it is retained because "breathing is
coming back as an assignable per-button-state effect". That is this workstream,
and authored breathing arrives as a program track rather than a single-frame
command. Delete the effect, the opcode, and its firmware and simulated-device
handling. The single-frame path carries transient feedback only; steady
appearance, animated or not, belongs to the program.

### `ButtonFeedbackColour` is replaced by a resolved value

`ApplicationState.button_feedback_colours` holds the closed enum, which cannot
express an authored colour. It becomes a resolved `ButtonFeedback(rgb, pulses)`,
with the three system treatments as named constants:

| Reason | Value |
| --- | --- |
| press rejected by configuration | `RGB_RED`, 2 pulses |
| Servotronic unavailable | `RGB_AMBER`, 2 pulses |
| button has no binding | `RGB_WHITE`, 1 pulse |
| press acknowledged, nothing changed | slot base colour at full, 1 pulse |

The duration branch in `domain/controller/reducer.py:114-118`, currently keyed on
`blink_colour is ButtonFeedbackColour.WHITE`, keys on pulse count instead.

### Affected surfaces

`protocol/custom.toml` and both generated outputs (`protocol/generated.py`,
`devices/button-pad/include/can_ids.h`), `adapters/output.py`, `domain/events.py`,
`domain/state.py`, `domain/controller/reducer.py`, `domain/controller/intents.py`,
`kernel/kernel.py`, the simulated pad in
`runners/simulation/devices/neotrellis.py`, the firmware in
`devices/button-pad/src/main.cpp`, and the protocol test vectors.

The browser is unaffected: it renders `buttons.program`, and feedback blinks are
already composed into the program by `ButtonLedProjection.effect`. The effect
frame is the low-latency hardware path only.

## API and live contract

- Generated command models in `api/models/button_profiles.py` are unchanged;
  presentation is a sibling of `command` in the slot model, not part of it.
- Slot presentation is validated at the save boundary alongside
  `validate_button_profile_for`: colour in range, animation bounds, and animation
  only on commands with an active predicate.
- The live contract publishes `buttons.program`, which is already track-based, so
  no live-contract shape change is needed.

## Frontend preview

`frontend/src/components/button-profile-editor/button-led-presentation.ts`
mirrors the Python derivation so the editor can preview an unsaved profile. That
duplication shrinks but does **not** disappear: the colour *table* goes away, but
the *active predicate* still has to be mirrored, because activeness depends both
on live steering state the browser holds and on the parameters of a command the
server has not seen. What remains is a mirror of the predicate producing a
`ButtonVisual`, plus a four-case switch over the authored values containing no
command knowledge at all. Keep the file, keep the "change both together" note,
and keep the constants pinned by `button-led-presentation.test.ts`.

## Required tests

- `colour × 8/255` reproduces `SOFT_WHITE` and `SOFT_AMBER` exactly.
- Each catalogue predicate against automatic, manual, and maximum-assistance
  states, including the parameterised cases (`select_steering_mode(auto)` active
  only in automatic; `set_manual_assistance_level(n)` active only at level `n`).
- Unavailable overrides active for a Servotronic-requiring command; does not
  override for one that does not require it.
- API rejects: out-of-range colour, breathe period outside 250–10 000,
  `minimum > maximum`, blink duration outside 1–10 000, animation on a command
  with no active predicate, and incomplete slot objects.
- An authored breathe produces a `BUTTON_PAD_TRACK_BREATHE` track with the
  expected packed `parameter_b`, and the existing program invariants
  (one replace-all, one commit, full coverage) still hold.
- The `intents.py` visible-change comparison fires an acknowledgement blink when
  no button's visual state changed, and does not fire when a *different* button
  changed — specifically, an `adjust_manual_assistance` press that flips a
  `set_manual_assistance_level(n)` button's active state.
- A slot's rendered track is unaffected by animation phase, so repeated
  `led_state` calls over a static application state compare equal.
- The generic blink command encodes the expected DLC-8 bytes for each of the four
  feedback reasons, and the acknowledgement case carries the slot's authored
  colour rather than white.
- The simulated pad and the firmware host tests render a 1-pulse and a 2-pulse
  blink of an arbitrary RGB, and reject a pulse count outside 1-2.
- No `breathe` opcode remains on `0x701`, and an authored breathe reaches the pad
  as a program track instead.
- Existing button-profile API, runtime, and SQLite suites regress.

## Acceptance criteria

- No hardcoded per-command colour remains in the coordinator or the frontend
  preview.
- A saved profile round-trips colour and animation through SQLite, HTTP, and the
  live contract, and the pad renders the authored values.
- `active_colour` is present, always `null`, and rejected if non-null.
- `0x701` carries exactly one opcode, and `ButtonFeedbackColour`,
  `SetButtonPadBreathe` and `triggerRedDoubleBlink` no longer exist.
