"""The button-pad LED projection derived from application state.

Given application state and the active button profile, this produces the complete
desired button-pad program in two steps: what each button is reporting
(:class:`ButtonLedState`), and the track that renders that report against the slot's
authored colour and animation. It reads state and never mutates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, assert_never

from e87canbus.domain.buttons.commands import button_command_is_active
from e87canbus.domain.buttons.pad import (
    ButtonPadTrackPayload,
    blink_track,
    breathe_track,
    resolved_button_pad_program,
    solid_track,
)
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    BlinkAnimation,
    BreatheAnimation,
    ButtonSlot,
)
from e87canbus.domain.events import (
    BUTTON_FEEDBACK_BLINK_OFF_MS,
    BUTTON_FEEDBACK_BLINK_ON_MS,
    BUTTON_LED_COUNT,
    ButtonLedState,
    SetButtonPadProgram,
)
from e87canbus.domain.intents import intent_requires_servotronic
from e87canbus.domain.state import (
    RGB_OFF,
    ApplicationState,
    ButtonVisual,
    Rgb,
)

# The one treatment that is not authorable, because its value is that it reads
# identically on every button: the resting override for a control the car cannot obey.
SOFT_AMBER: Rgb = (8, 6, 0)

# The resting brightness an inactive button is scaled down to. It is the level the pad
# has always rested at - the retired ``SOFT_WHITE`` was white at exactly this level -
# so authoring a colour changes which hue rests, not how dim resting is.
RESTING_BRIGHTNESS: int = 8

# Indefinite: an authored animation runs for as long as its button is active, and the
# button ceasing to be active is what replaces the track.
_AUTHORED_REPEAT = 0


def resting_rgb(rgb: Rgb) -> Rgb:
    """Scale an authored colour down to the pad's resting brightness.

    Rounded to the nearest byte rather than truncated, because the constants this has
    to keep reproducing were written that way: ``SOFT_AMBER`` is ``(8, 6, 0)`` while
    ``RGB_AMBER``'s green channel of 191 is 5.99 at this scale, so truncation would
    move the amber resting colour a step darker than the pad has ever shown it.
    """

    red, green, blue = rgb
    return (
        (red * RESTING_BRIGHTNESS + 127) // 255,
        (green * RESTING_BRIGHTNESS + 127) // 255,
        (blue * RESTING_BRIGHTNESS + 127) // 255,
    )


class ButtonLedPresenter(Protocol):
    """Replaceable seam for deriving LED presentation from a button profile."""

    def __call__(
        self,
        state: ApplicationState,
        profile: ActiveButtonProfile,
        servotronic_usable: bool,
    ) -> ButtonLedState: ...


def derived_button_led_state(
    state: ApplicationState,
    profile: ActiveButtonProfile,
    servotronic_usable: bool = True,
) -> ButtonLedState:
    """Derive what each button reports, never from its index and never as a colour.

    The order is a priority order: a button the car cannot obey says so regardless of
    what its command's condition would otherwise report, and a command with no
    observable condition is simply never active.
    """

    visuals = [ButtonVisual.UNASSIGNED] * BUTTON_LED_COUNT
    for index, slot in profile.assigned():
        command = slot.command
        if not servotronic_usable and intent_requires_servotronic(command):
            visuals[index] = ButtonVisual.UNAVAILABLE
        elif button_command_is_active(state, command):
            visuals[index] = ButtonVisual.ACTIVE
        else:
            visuals[index] = ButtonVisual.INACTIVE
    return ButtonLedState(tuple(visuals))


def rendered_button_track(
    slot: ButtonSlot | None,
    visual: ButtonVisual,
) -> ButtonPadTrackPayload:
    """Render one button from its authored values and the state it is reporting.

    This is the whole of the colour decision, and it holds no knowledge of any
    command: which appearance applies was decided by the derivation, and which pixels
    that appearance uses was decided by whoever authored the slot.
    """

    if visual is ButtonVisual.UNASSIGNED:
        return solid_track(RGB_OFF)
    # Only an empty slot derives UNASSIGNED, so every other state has authored values.
    # A replaceable presenter can break that agreement, so it fails as a value error
    # rather than an assertion that -O would strip into an AttributeError.
    if slot is None:
        raise ValueError(f"{visual} requires an assigned slot")
    match visual:
        case ButtonVisual.UNAVAILABLE:
            return solid_track(SOFT_AMBER)
        case ButtonVisual.ACTIVE:
            return _active_track(slot)
        case ButtonVisual.INACTIVE:
            # Static always: an authored animation renders the active state alone.
            return solid_track(resting_rgb(slot.colour))
        case _:
            assert_never(visual)


def _active_track(slot: ButtonSlot) -> ButtonPadTrackPayload:
    # ``active_colour`` is reserved and always ``None``, which means "``colour`` at
    # full brightness"; resolving it here is where a second authored colour lands.
    colour = slot.active_colour if slot.active_colour is not None else slot.colour
    match slot.animation:
        case None:
            return solid_track(colour)
        case BreatheAnimation(period_ms=period_ms, minimum=minimum, maximum=maximum):
            return breathe_track(colour, minimum, maximum, period_ms, _AUTHORED_REPEAT, colour)
        case BlinkAnimation(on_ms=on_ms, off_ms=off_ms):
            return blink_track(colour, on_ms, off_ms, _AUTHORED_REPEAT, colour)
        case _:
            assert_never(slot.animation)


@dataclass(frozen=True)
class ButtonLedProjection:
    """The profile and presentation seam every LED derivation is computed against.

    Carrying the profile in one value keeps it a required argument on every path, so
    a decision can never be computed against the compiled-in default while the pad is
    running a user profile.
    """

    profile: ActiveButtonProfile
    servotronic_usable: bool = True
    presenter: ButtonLedPresenter = derived_button_led_state

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ActiveButtonProfile):
            raise TypeError("profile must be an ActiveButtonProfile")
        if type(self.servotronic_usable) is not bool:
            raise ValueError("servotronic_usable must be a boolean")

    def led_state(self, state: ApplicationState) -> ButtonLedState:
        """What each button is reporting, before any transient track is applied."""

        return self.presenter(state, self.profile, self.servotronic_usable)

    def effect(self, state: ApplicationState) -> SetButtonPadProgram:
        """Return the complete device program: authored steady tracks plus feedback.

        The frozen ``SetButtonPadProgram`` result is shareable, so callers that need
        it more than once in a single commit compute it once and reuse the local.
        """

        visuals = self.led_state(state).visuals
        tracks = [
            rendered_button_track(slot, visual)
            for slot, visual in zip(self.profile.slots, visuals, strict=True)
        ]
        for index, feedback in enumerate(state.button_feedback):
            if feedback is not None:
                tracks[index] = blink_track(
                    feedback.rgb,
                    BUTTON_FEEDBACK_BLINK_ON_MS,
                    BUTTON_FEEDBACK_BLINK_OFF_MS,
                    feedback.pulses,
                    # A blink resolves back to the steady appearance beneath it, which
                    # an animation makes a track rather than a colour; the pad restores
                    # a final colour only, so it rests at the animation's own colour.
                    tracks[index].rgb,
                )
        return SetButtonPadProgram(resolved_button_pad_program(tuple(tracks)))
