"""The button-pad LED projection derived from application state.

Given application state and the active button profile, this produces the complete
desired button-pad program: the steady per-button colours plus any active
feedback-blink tracks. It reads state and never mutates it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from e87canbus.domain.buttons.catalogue import ButtonCommandPresentation
from e87canbus.domain.buttons.commands import button_command_presentation
from e87canbus.domain.buttons.pad import (
    blink_track,
    resolved_button_pad_program,
    solid_track,
)
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.events import (
    BUTTON_FEEDBACK_BLINK_OFF_MS,
    BUTTON_FEEDBACK_BLINK_ON_MS,
    BUTTON_LED_COUNT,
    RGB_AMBER,
    RGB_BLUE,
    RGB_OFF,
    RGB_RED,
    RGB_WHITE,
    ButtonFeedbackColour,
    ButtonLedState,
    SetButtonPadProgram,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode

SOFT_WHITE: tuple[int, int, int] = (8, 8, 8)
SOFT_AMBER: tuple[int, int, int] = (8, 6, 0)


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
    """Derive colours from each slot's catalogue presentation, never from its index."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    maximum_active = isinstance(steering, MaximumAssistance)
    colours = [RGB_OFF] * BUTTON_LED_COUNT
    for index, slot in profile.assigned():
        presentation = button_command_presentation(slot.command)
        if presentation is ButtonCommandPresentation.STEERING_MODE:
            colour = (
                RGB_BLUE
                if servotronic_usable and mode is SteeringMode.AUTO
                else RGB_AMBER
                if servotronic_usable
                else SOFT_AMBER
            )
        elif presentation is ButtonCommandPresentation.MAXIMUM_ASSISTANCE and maximum_active:
            colour = RGB_WHITE
        elif presentation in (
            ButtonCommandPresentation.STEERING_ADJUSTMENT,
            ButtonCommandPresentation.MAXIMUM_ASSISTANCE,
        ):
            colour = SOFT_WHITE if servotronic_usable else SOFT_AMBER
        else:
            colour = SOFT_WHITE
        colours[index] = colour
    return ButtonLedState(tuple(colours))


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
        """The steady colours an operator sees, before any timed track is applied."""

        return self.presenter(state, self.profile, self.servotronic_usable)

    def effect(self, state: ApplicationState) -> SetButtonPadProgram:
        """Return the complete device program; static RGB remains the normal case.

        The frozen ``SetButtonPadProgram`` result is shareable, so callers that need
        it more than once in a single commit compute it once and reuse the local.
        """

        displayed = self.led_state(state).rgb
        tracks = [solid_track(rgb) for rgb in displayed]
        feedback_rgb = {
            ButtonFeedbackColour.RED: RGB_RED,
            ButtonFeedbackColour.AMBER: RGB_AMBER,
            ButtonFeedbackColour.WHITE: RGB_WHITE,
        }
        for index, colour in enumerate(state.button_feedback_colours):
            if colour is not None:
                tracks[index] = blink_track(
                    feedback_rgb[colour],
                    BUTTON_FEEDBACK_BLINK_ON_MS,
                    BUTTON_FEEDBACK_BLINK_OFF_MS,
                    1 if colour is ButtonFeedbackColour.WHITE else 2,
                    displayed[index],
                )
        return SetButtonPadProgram(resolved_button_pad_program(tuple(tracks)))

    def maximum_assistance_indexes(self) -> tuple[int, ...]:
        """Every button whose colour carries the maximum-assistance indicator.

        A profile may show that indicator on no button or on several, so callers ask
        the profile rather than assuming the built-in index.
        """

        return tuple(
            index
            for index, slot in self.profile.assigned()
            if button_command_presentation(slot.command)
            is ButtonCommandPresentation.MAXIMUM_ASSISTANCE
        )
