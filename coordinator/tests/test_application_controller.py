from dataclasses import FrozenInstanceError

import pytest
from e87canbus.application.controller import (
    ApplicationSnapshot,
    initial_effects,
    normalize_state,
    snapshot,
    transition,
)
from e87canbus.application.events import (
    ButtonPressed,
    ControlTimerElapsed,
    LedColour,
    SetButtonLed,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    NormalSteering,
    SpeedSample,
    SteeringMode,
)
from e87canbus.config import CanNetwork, SteeringConfig

CONFIG = SteeringConfig()


def application_state(
    mode: SteeringMode = SteeringMode.AUTO,
    manual_level: int = 0,
) -> ApplicationState:
    return ApplicationState(steering=NormalSteering(mode, manual_level))


def projection(state: ApplicationState) -> tuple[SteeringMode, int, bool]:
    value = snapshot(state, CONFIG)
    return (
        value.steering_mode,
        value.manual_assistance_level,
        value.maximum_assistance_active,
    )


def colours(state: ApplicationState, button_index: int) -> tuple[LedColour, ...]:
    return tuple(
        effect.colour
        for effect in transition(state, ButtonPressed(button_index), CONFIG).effects
    )


def test_initial_snapshot_and_effects() -> None:
    state = ApplicationState()

    assert snapshot(state, CONFIG) == ApplicationSnapshot(
        vehicle_speed_kph=0.0,
        steering_mode=SteeringMode.AUTO,
        manual_assistance_level=0,
        maximum_assistance_active=False,
        speed_valid=False,
    )
    assert initial_effects(state, CONFIG) == (
        SetButtonLed(0, LedColour.BLUE),
        SetButtonLed(3, LedColour.OFF),
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
    )


@pytest.mark.parametrize(
    ("initial_mode", "button_index", "expected", "effect_colours"),
    [
        (SteeringMode.AUTO, 0, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (SteeringMode.AUTO, 1, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (SteeringMode.AUTO, 2, (SteeringMode.MANUAL, 0, False), (LedColour.AMBER,)),
        (
            SteeringMode.AUTO,
            3,
            (SteeringMode.MANUAL, 7, True),
            (LedColour.AMBER, LedColour.WHITE),
        ),
        (SteeringMode.MANUAL, 0, (SteeringMode.AUTO, 0, False), (LedColour.BLUE,)),
        (SteeringMode.MANUAL, 1, (SteeringMode.MANUAL, 0, False), ()),
        (SteeringMode.MANUAL, 2, (SteeringMode.MANUAL, 1, False), ()),
        (
            SteeringMode.MANUAL,
            3,
            (SteeringMode.MANUAL, 7, True),
            (LedColour.AMBER, LedColour.WHITE),
        ),
    ],
)
def test_mapped_buttons_from_normal_modes(
    initial_mode: SteeringMode,
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    effect_colours: tuple[LedColour, ...],
) -> None:
    state = application_state(mode=initial_mode)

    result = transition(state, ButtonPressed(button_index), CONFIG)

    assert projection(result.state) == expected
    assert tuple(effect.colour for effect in result.effects) == effect_colours


@pytest.mark.parametrize(
    ("button_index", "expected", "effect_colours"),
    [
        (0, (SteeringMode.MANUAL, 7, True), ()),
        (1, (SteeringMode.MANUAL, 3, False), (LedColour.AMBER, LedColour.OFF)),
        (2, (SteeringMode.MANUAL, 3, False), (LedColour.AMBER, LedColour.OFF)),
        (3, (SteeringMode.AUTO, 3, False), (LedColour.BLUE, LedColour.OFF)),
    ],
)
def test_mapped_buttons_while_maximum_assistance_is_active(
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    effect_colours: tuple[LedColour, ...],
) -> None:
    state = ApplicationState(MaximumAssistance(NormalSteering(manual_level=3)))

    result = transition(state, ButtonPressed(button_index), CONFIG)

    assert projection(result.state) == expected
    assert tuple(effect.colour for effect in result.effects) == effect_colours


def test_maximum_assistance_restores_previous_manual_state() -> None:
    state = application_state(SteeringMode.MANUAL, 5)

    enabled = transition(state, ButtonPressed(3), CONFIG).state
    restored = transition(enabled, ButtonPressed(3), CONFIG).state

    assert projection(restored) == (SteeringMode.MANUAL, 5, False)


def test_first_assistance_press_after_maximum_only_restores_level() -> None:
    state = ApplicationState(MaximumAssistance(NormalSteering(manual_level=3)))

    restored = transition(state, ButtonPressed(2), CONFIG).state
    adjusted = transition(restored, ButtonPressed(2), CONFIG).state

    assert snapshot(restored, CONFIG).manual_assistance_level == 3
    assert snapshot(adjusted, CONFIG).manual_assistance_level == 4


def test_unknown_button_is_a_no_op() -> None:
    state = ApplicationState()

    assert transition(state, ButtonPressed(9), CONFIG).state is state


def test_manual_assistance_is_clamped_to_configured_bounds() -> None:
    config = SteeringConfig(manual_level_count=3)
    state = normalize_state(application_state(SteeringMode.MANUAL, -4), config)

    state = transition(state, ButtonPressed(1), config).state
    for _ in range(4):
        state = transition(state, ButtonPressed(2), config).state

    assert snapshot(state, config).manual_assistance_level == 2


@pytest.mark.parametrize(
    ("evaluation_time", "expected_valid"),
    [(10.5, True), (11.0, True), (11.000_001, False)],
)
def test_speed_validity_is_derived_from_sample_age(
    evaluation_time: float,
    expected_valid: bool,
) -> None:
    observed = SpeedObserved(SpeedSample(42.5, 10.0, CanNetwork.FCAN))
    state = transition(ApplicationState(), observed, CONFIG).state

    state = transition(state, ControlTimerElapsed(evaluation_time), CONFIG).state

    value = snapshot(state, CONFIG)
    assert value.vehicle_speed_kph == 42.5
    assert value.speed_valid is expected_valid


def test_regressing_timer_cannot_make_stale_speed_valid() -> None:
    state = transition(
        ApplicationState(),
        SpeedObserved(SpeedSample(42.5, 1.0, CanNetwork.FCAN)),
        CONFIG,
    ).state
    stale = transition(state, ControlTimerElapsed(5.0), CONFIG).state

    result = transition(stale, ControlTimerElapsed(1.5), CONFIG)

    assert result.state.speed_evaluated_at == 5.0
    assert snapshot(result.state, CONFIG).speed_valid is False
    assert result.effects == (
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_STALE),
    )


def test_speed_sample_clamps_negative_speed_and_retains_observation() -> None:
    sample = SpeedSample(-2.0, 12.5, CanNetwork.PTCAN)

    result = transition(ApplicationState(), SpeedObserved(sample), CONFIG)

    assert result.state.speed_sample == SpeedSample(0.0, 12.5, CanNetwork.PTCAN)
    assert snapshot(result.state, CONFIG).speed_valid is True
    assert result.effects == ()


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            ApplicationState(),
            SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
        ),
        (
            application_state(SteeringMode.MANUAL, 4),
            SetSteeringAssistance(4 / 7, SteeringCommandReason.MANUAL),
        ),
        (
            ApplicationState(MaximumAssistance(NormalSteering())),
            SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM),
        ),
    ],
)
def test_control_timer_selects_bounded_steering_command(
    state: ApplicationState,
    expected: SetSteeringAssistance,
) -> None:
    result = transition(state, ControlTimerElapsed(1.0), CONFIG)

    assert result.effects == (expected,)


def test_fresh_speed_selects_interpolated_auto_assistance() -> None:
    state = transition(
        ApplicationState(),
        SpeedObserved(SpeedSample(15.0, 1.0, CanNetwork.FCAN)),
        CONFIG,
    ).state

    result = transition(state, ControlTimerElapsed(1.5), CONFIG)

    assert len(result.effects) == 1
    command = result.effects[0]
    assert isinstance(command, SetSteeringAssistance)
    assert command.assistance == pytest.approx(5 / 6)
    assert command.reason is SteeringCommandReason.AUTO


@pytest.mark.parametrize(
    ("reason", "command_reason"),
    [
        (
            SteeringFallbackReason.CAN_READER_FAILURE,
            SteeringCommandReason.CAN_READER_FAILURE,
        ),
        (
            SteeringFallbackReason.INBOX_OVERFLOW,
            SteeringCommandReason.INBOX_OVERFLOW,
        ),
        (SteeringFallbackReason.SHUTDOWN, SteeringCommandReason.SHUTDOWN),
    ],
)
def test_fallback_inputs_select_zero_assistance(
    reason: SteeringFallbackReason,
    command_reason: SteeringCommandReason,
) -> None:
    result = transition(
        application_state(SteeringMode.MANUAL, 7),
        SteeringFallbackRequested(reason),
        CONFIG,
    )

    assert result.effects == (SetSteeringAssistance(0.0, command_reason),)


def test_transition_is_deterministic_and_does_not_mutate_input() -> None:
    state = ApplicationState()
    event = ButtonPressed(0)

    first = transition(state, event, CONFIG)
    second = transition(state, event, CONFIG)

    assert first == second
    assert first.state is not state
    assert projection(state) == (SteeringMode.AUTO, 0, False)
    with pytest.raises(FrozenInstanceError):
        state.speed_evaluated_at = 1.0  # type: ignore[misc]
