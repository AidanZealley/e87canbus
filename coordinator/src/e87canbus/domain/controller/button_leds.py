"""The button-pad LED projection derived from application state.

Given application state, this produces the complete desired button-pad program:
the steady per-button colours plus any active demo-breathe or feedback-blink
tracks. It reads state and never mutates it.
"""

from __future__ import annotations

from typing import Protocol

from e87canbus.config import HighBeamStrobeConfig
from e87canbus.domain.button_bindings import ButtonBindingProfile, built_in_button_binding_profile
from e87canbus.domain.button_pad import (
    ButtonPadProgram,
    blink_track,
    breathe_track,
    resolved_button_pad_program,
    solid_track,
)
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
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleButtonPadDemoBreathe,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode

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


class ButtonLedPresenter(Protocol):
    """Replaceable seam for deriving LED presentation from a binding profile."""

    def __call__(
        self,
        state: ApplicationState,
        profile: ButtonBindingProfile,
        servotronic_usable: bool,
    ) -> ButtonLedState: ...


def derived_button_led_state(
    state: ApplicationState,
    profile: ButtonBindingProfile,
    servotronic_usable: bool = True,
) -> ButtonLedState:
    """Derive default colours from intent semantics, independent of button indexes."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    colours = [RGB_OFF] * BUTTON_LED_COUNT
    for binding in profile.bindings:
        intent = binding.press_intent
        colour = SOFT_WHITE
        if isinstance(intent, (ToggleAutomaticAssistance, SelectSteeringMode)):
            colour = (
                RGB_BLUE
                if servotronic_usable and mode is SteeringMode.AUTO
                else RGB_AMBER
                if servotronic_usable
                else SOFT_AMBER
            )
        elif isinstance(
            intent,
            (
                AdjustManualAssistance,
                SetManualAssistanceLevel,
                SetMaximumAssistance,
                ToggleMaximumAssistance,
            ),
        ):
            colour = (
                RGB_WHITE
                if isinstance(intent, (SetMaximumAssistance, ToggleMaximumAssistance))
                and isinstance(state.steering, MaximumAssistance)
                else SOFT_AMBER
                if not servotronic_usable
                else SOFT_WHITE
            )
        elif isinstance(intent, (StartHighBeamStrobe, ToggleButtonPadDemoBreathe)):
            colour = SOFT_WHITE
        colours[binding.button_index] = colour
    return ButtonLedState(tuple(colours))


def button_led_state(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
    profile: ButtonBindingProfile | None = None,
    presenter: ButtonLedPresenter = derived_button_led_state,
) -> ButtonLedState:
    """Derive the complete button-pad LED projection from application state."""
    selected = profile or built_in_button_binding_profile(
        HighBeamStrobeConfig(button_index=high_beam_button_index)
    )
    return presenter(state, selected, servotronic_usable)


def button_led_effect(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
    profile: ButtonBindingProfile | None = None,
    presenter: ButtonLedPresenter = derived_button_led_state,
) -> SetButtonPadProgram:
    """Return the complete device program; static RGB remains the normal case.

    The frozen ``SetButtonPadProgram`` result is shareable, so callers that need
    it more than once in a single commit compute it once and reuse the local.
    """

    selected = profile or built_in_button_binding_profile(
        HighBeamStrobeConfig(button_index=high_beam_button_index)
    )
    displayed = presenter(state, selected, servotronic_usable).rgb
    tracks = [solid_track(rgb) for rgb in displayed]
    breathe_index = next(
        (
            binding.button_index
            for binding in selected.bindings
            if isinstance(binding.press_intent, ToggleButtonPadDemoBreathe)
        ),
        None,
    )
    if state.button_pad_demo_breathe_enabled and breathe_index is not None:
        tracks[breathe_index] = breathe_track(
            DEMO_BREATHE_RGB,
            DEMO_BREATHE_MINIMUM_BRIGHTNESS,
            DEMO_BREATHE_MAXIMUM_BRIGHTNESS,
            DEMO_BREATHE_PERIOD_MS,
            final_rgb=displayed[breathe_index],
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
    profile: ButtonBindingProfile | None = None,
    presenter: ButtonLedPresenter = derived_button_led_state,
) -> ButtonPadProgram:
    return button_led_effect(
        state, servotronic_usable, high_beam_button_index, profile, presenter
    ).program
