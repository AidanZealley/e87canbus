"""The rendering rule: what a button reports, and what the authored values make of it.

The derivation and the rendering are deliberately separate here, because they are
separate concerns: which of a slot's appearances applies is decided from application
state, and which pixels that appearance uses is decided by whoever authored the slot.
"""

from collections.abc import Mapping

from e87canbus.config import HighBeamStrobeConfig, SteeringConfig
from e87canbus.domain.buttons.pad import resolve_button_pad_tracks, solid_track
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    BlinkAnimation,
    BreatheAnimation,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.controller import (
    SOFT_AMBER,
    ButtonLedProjection,
    derived_button_led_state,
    execute_operator_intent,
    finish_button_intent,
    resting_rgb,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    StartHighBeamStrobe,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import (
    RGB_AMBER,
    RGB_BLUE,
    RGB_OFF,
    RGB_WHITE,
    ApplicationState,
    ButtonFeedback,
    ButtonVisual,
    MaximumAssistance,
    NormalSteering,
    SteeringMode,
)
from e87canbus.domain.steering.curves import default_steering_curve_definition
from e87canbus.protocol.can import (
    BUTTON_PAD_TRACK_BLINK,
    BUTTON_PAD_TRACK_BREATHE,
    decode_button_pad_program,
)

CONFIG = SteeringConfig()
CURVE = default_steering_curve_definition()
STROBE = HighBeamStrobeConfig()
# An arbitrary authored colour that is none of the system values, so a test that sees
# it knows the pixels came from the slot rather than from a table.
AUTHORED = (10, 20, 30)


def profile(assignments: Mapping[int, ButtonSlot]) -> ActiveButtonProfile:
    return ActiveButtonProfile("user", button_profile_definition_with(dict(assignments)))


def manual(level: int = 0) -> ApplicationState:
    return ApplicationState(NormalSteering(SteeringMode.MANUAL, level))


def test_resting_scale_reproduces_the_constants_the_pad_has_always_shown() -> None:
    assert resting_rgb(RGB_WHITE) == (8, 8, 8)
    assert resting_rgb(RGB_AMBER) == (8, 6, 0)
    assert resting_rgb(RGB_AMBER) == SOFT_AMBER
    assert resting_rgb(RGB_OFF) == RGB_OFF


def test_each_visual_state_is_derived_from_the_bound_command_and_its_parameters() -> None:
    selected = profile(
        {
            0: ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), RGB_BLUE),
            1: ButtonSlot(SelectSteeringMode(SteeringMode.MANUAL), RGB_BLUE),
            2: ButtonSlot(AdjustManualAssistance(1), RGB_WHITE),
        }
    )

    automatic = derived_button_led_state(ApplicationState(), selected).visuals
    manual_states = derived_button_led_state(manual(), selected).visuals

    assert automatic[0] is ButtonVisual.ACTIVE
    assert automatic[1] is ButtonVisual.INACTIVE
    assert manual_states[0] is ButtonVisual.INACTIVE
    assert manual_states[1] is ButtonVisual.ACTIVE
    # A relative step has no condition, and an empty slot has no command at all.
    assert automatic[2] is ButtonVisual.INACTIVE
    assert automatic[3] is ButtonVisual.UNASSIGNED


def test_maximum_assistance_reports_as_manual_to_a_mode_question() -> None:
    selected = profile(
        {
            0: ButtonSlot(SelectSteeringMode(SteeringMode.MANUAL), RGB_BLUE),
            1: ButtonSlot(ToggleMaximumAssistance(), RGB_WHITE),
        }
    )
    state = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.AUTO)))

    visuals = derived_button_led_state(state, selected).visuals

    assert visuals[0] is ButtonVisual.ACTIVE
    assert visuals[1] is ButtonVisual.ACTIVE


def test_unavailable_overrides_active_only_where_the_command_needs_servotronic() -> None:
    selected = profile(
        {
            0: ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), RGB_BLUE),
            1: ButtonSlot(StartHighBeamStrobe(), RGB_WHITE),
        }
    )

    visuals = derived_button_led_state(ApplicationState(), selected, False).visuals

    assert visuals[0] is ButtonVisual.UNAVAILABLE
    assert visuals[1] is ButtonVisual.INACTIVE


def test_every_visual_state_renders_from_the_authored_colour_or_a_system_value() -> None:
    selected = profile(
        {
            0: ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), AUTHORED),
            1: ButtonSlot(SelectSteeringMode(SteeringMode.MANUAL), AUTHORED),
        }
    )

    usable = resolve_button_pad_tracks(
        ButtonLedProjection(selected).effect(ApplicationState()).program
    )
    unusable = resolve_button_pad_tracks(
        ButtonLedProjection(selected, False).effect(ApplicationState()).program
    )

    assert usable[0] == solid_track(AUTHORED)
    assert usable[1] == solid_track(resting_rgb(AUTHORED))
    assert usable[2] == solid_track(RGB_OFF)
    # The one treatment that is not authorable, so it reads the same on every button.
    assert unusable[0] == unusable[1] == solid_track(SOFT_AMBER)


def test_an_authored_breathe_reaches_the_pad_as_an_indefinite_breathe_track() -> None:
    animation = BreatheAnimation(2_000, 8, 255)
    selected = profile(
        {5: ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), AUTHORED, None, animation)}
    )

    program = ButtonLedProjection(selected).effect(ApplicationState()).program
    tracks = resolve_button_pad_tracks(program)

    assert tracks[5].kind == BUTTON_PAD_TRACK_BREATHE
    assert tracks[5].rgb == AUTHORED
    assert tracks[5].parameter_a == 2_000
    assert tracks[5].parameter_b == 8 | (255 << 8)
    assert tracks[5].repeat == 0
    commands = tuple(decode_button_pad_program(payload) for payload in program.payloads)
    assert [command.replace_all for command in commands].count(True) == 1
    assert [command.commit for command in commands].count(True) == 1
    covered = 0
    for command in commands:
        covered |= command.target_mask
    assert covered == 0xFFFF


def test_an_authored_blink_renders_only_while_the_button_is_active() -> None:
    animation = BlinkAnimation(400, 400)
    selected = profile(
        {5: ButtonSlot(SelectSteeringMode(SteeringMode.AUTO), AUTHORED, None, animation)}
    )
    projection = ButtonLedProjection(selected)

    active = resolve_button_pad_tracks(projection.effect(ApplicationState()).program)
    inactive = resolve_button_pad_tracks(projection.effect(manual()).program)

    assert active[5].kind == BUTTON_PAD_TRACK_BLINK
    assert active[5].repeat == 0
    # The inactive state is always static and faint, whatever the slot authored.
    assert inactive[5] == solid_track(resting_rgb(AUTHORED))


def press(
    state: ApplicationState,
    selected: ActiveButtonProfile,
    button_index: int,
) -> ApplicationState:
    """Run one button press end to end through the intent and presentation layers."""

    leds = ButtonLedProjection(selected)
    command = selected.intent_for_press(button_index)
    assert command is not None
    result = execute_operator_intent(state, command, CONFIG, leds)
    return finish_button_intent(state, result, button_index, 1.0, CONFIG, CURVE, STROBE, leds).state


def test_a_press_that_moves_nothing_flashes_the_pressed_slot_authored_colour() -> None:
    # A downward step already at the bottom of the range changes no state at all.
    selected = profile({0: ButtonSlot(AdjustManualAssistance(-1), AUTHORED)})

    pressed = press(manual(), selected, 0)

    assert pressed.button_feedback[0] == ButtonFeedback(AUTHORED, 1)


def test_a_press_that_relights_a_different_button_is_not_also_acknowledged() -> None:
    # The pressed button itself never changes - a relative step has no condition - but
    # the level it moves reports itself elsewhere on the pad, which is real feedback.
    selected = profile(
        {
            0: ButtonSlot(AdjustManualAssistance(1), AUTHORED),
            9: ButtonSlot(SetManualAssistanceLevel(1), RGB_WHITE),
        }
    )
    state = manual()

    assert derived_button_led_state(state, selected).visuals[9] is ButtonVisual.INACTIVE
    pressed = press(state, selected, 0)

    assert derived_button_led_state(pressed, selected).visuals[9] is ButtonVisual.ACTIVE
    assert pressed.button_feedback[0] is None
