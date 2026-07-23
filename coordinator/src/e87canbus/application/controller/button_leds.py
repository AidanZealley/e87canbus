"""The button-pad LED projection derived from application state.

Given application state, this produces the complete desired button-pad program:
the steady per-button colours plus any active demo-breathe or feedback-blink
tracks. It reads state and never mutates it.
"""

from __future__ import annotations

from e87canbus.application.events import (
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
from e87canbus.application.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.button_pad import (
    ButtonPadProgram,
    blink_track,
    breathe_track,
    resolved_button_pad_program,
    solid_track,
)
from e87canbus.config import HighBeamStrobeConfig

STEERING_MODE_BUTTON_INDEX = 0
MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3
DEMO_BREATHE_BUTTON_INDEX = 15
SERVOTRONIC_BUTTON_INDEXES = frozenset({0, 1, 2, 3})
SOFT_WHITE: tuple[int, int, int] = (8, 8, 8)
SOFT_AMBER: tuple[int, int, int] = (8, 6, 0)
DEMO_BREATHE_RGB: tuple[int, int, int] = (0, 220, 255)
DEMO_BREATHE_MINIMUM_BRIGHTNESS = 20
DEMO_BREATHE_MAXIMUM_BRIGHTNESS = 255
DEMO_BREATHE_PERIOD_MS = 1600


def button_led_state(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> ButtonLedState:
    """Derive the complete button-pad LED projection from application state."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    mode_colour = (
        RGB_BLUE
        if servotronic_usable and mode is SteeringMode.AUTO
        else RGB_AMBER
        if servotronic_usable
        else SOFT_AMBER
    )
    maximum_colour = (
        RGB_WHITE
        if servotronic_usable and isinstance(state.steering, MaximumAssistance)
        else RGB_OFF
    )
    assigned_buttons = SERVOTRONIC_BUTTON_INDEXES | {
        high_beam_button_index,
        DEMO_BREATHE_BUTTON_INDEX,
    }
    normal = tuple(
        mode_colour
        if index == STEERING_MODE_BUTTON_INDEX
        else maximum_colour
        if index == MAXIMUM_ASSISTANCE_BUTTON_INDEX and maximum_colour != RGB_OFF
        else SOFT_AMBER
        if index in SERVOTRONIC_BUTTON_INDEXES and not servotronic_usable
        else SOFT_WHITE
        if index in assigned_buttons
        else RGB_OFF
        for index in range(BUTTON_LED_COUNT)
    )
    return ButtonLedState(normal)


def button_led_effect(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> SetButtonPadProgram:
    """Return the complete device program; static RGB remains the normal case.

    The frozen ``SetButtonPadProgram`` result is shareable, so callers that need
    it more than once in a single commit compute it once and reuse the local.
    """

    displayed = button_led_state(state, servotronic_usable, high_beam_button_index).rgb
    tracks = [solid_track(rgb) for rgb in displayed]
    if state.button_pad_demo_breathe_enabled:
        tracks[DEMO_BREATHE_BUTTON_INDEX] = breathe_track(
            DEMO_BREATHE_RGB,
            DEMO_BREATHE_MINIMUM_BRIGHTNESS,
            DEMO_BREATHE_MAXIMUM_BRIGHTNESS,
            DEMO_BREATHE_PERIOD_MS,
            final_rgb=displayed[DEMO_BREATHE_BUTTON_INDEX],
        )
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


def button_pad_program(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> ButtonPadProgram:
    return button_led_effect(state, servotronic_usable, high_beam_button_index).program
