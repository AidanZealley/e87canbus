import pytest
from e87canbus.application.controller import DEMO_BREATHE_BUTTON_INDEX, execute_operator_intent
from e87canbus.application.events import SetButtonPadBreathe, SetHighBeam
from e87canbus.application.intents import (
    AdjustManualAssistance,
    OperatorIntentContext,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleButtonPadDemoBreathe,
    ToggleMaximumAssistance,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    NormalSteering,
    SteeringMode,
)
from e87canbus.config import HighBeamStrobeConfig, SteeringConfig

CONFIG = SteeringConfig(manual_level_count=11)


def steering(state: ApplicationState) -> NormalSteering:
    assert isinstance(state.steering, NormalSteering)
    return state.steering


@pytest.mark.parametrize("delta", [-1, 1])
def test_first_adjustment_from_auto_enters_saved_manual_without_adjusting(delta: int) -> None:
    initial = ApplicationState(NormalSteering(SteeringMode.AUTO, 4))

    first = execute_operator_intent(initial, AdjustManualAssistance(delta), CONFIG).state
    second = execute_operator_intent(first, AdjustManualAssistance(delta), CONFIG).state

    assert steering(first) == NormalSteering(SteeringMode.MANUAL, 4)
    assert steering(second).manual_level == 4 + delta


@pytest.mark.parametrize("delta", [-1, 1])
def test_first_adjustment_from_maximum_restores_saved_manual_without_adjusting(
    delta: int,
) -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.AUTO, 4)))

    first = execute_operator_intent(initial, AdjustManualAssistance(delta), CONFIG).state
    second = execute_operator_intent(first, AdjustManualAssistance(delta), CONFIG).state

    assert steering(first) == NormalSteering(SteeringMode.MANUAL, 4)
    assert steering(second).manual_level == 4 + delta


def test_exact_manual_selection_clears_maximum_and_sets_requested_level() -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.AUTO, 8)))

    result = execute_operator_intent(
        initial,
        SetManualAssistanceLevel(2),
        CONFIG,
    )

    assert steering(result.state) == NormalSteering(SteeringMode.MANUAL, 2)


def test_exact_auto_selection_clears_maximum_and_retains_saved_level() -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.MANUAL, 8)))

    result = execute_operator_intent(
        initial,
        SelectSteeringMode(SteeringMode.AUTO),
        CONFIG,
    )

    assert steering(result.state) == NormalSteering(SteeringMode.AUTO, 8)


def test_manual_adjustments_stop_at_configured_level_bounds() -> None:
    low = ApplicationState(NormalSteering(SteeringMode.MANUAL, 0))
    high = ApplicationState(NormalSteering(SteeringMode.MANUAL, 10))

    lowered = execute_operator_intent(low, AdjustManualAssistance(-1), CONFIG).state
    raised = execute_operator_intent(high, AdjustManualAssistance(1), CONFIG).state

    assert steering(lowered).manual_level == 0
    assert steering(raised).manual_level == 10


def test_toggle_semantics_are_owned_by_the_same_executor() -> None:
    normal = ApplicationState(NormalSteering(SteeringMode.MANUAL, 6))

    automatic = execute_operator_intent(normal, ToggleAutomaticAssistance(), CONFIG).state
    maximum = execute_operator_intent(automatic, ToggleMaximumAssistance(), CONFIG).state
    restored = execute_operator_intent(maximum, ToggleMaximumAssistance(), CONFIG).state

    assert steering(automatic) == NormalSteering(SteeringMode.AUTO, 6)
    assert isinstance(maximum.steering, MaximumAssistance)
    assert restored == automatic


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        (NormalSteering(SteeringMode.AUTO, 4), NormalSteering(SteeringMode.MANUAL, 4)),
        (NormalSteering(SteeringMode.MANUAL, 4), NormalSteering(SteeringMode.AUTO, 4)),
        (
            MaximumAssistance(NormalSteering(SteeringMode.AUTO, 4)),
            NormalSteering(SteeringMode.AUTO, 4),
        ),
        (
            MaximumAssistance(NormalSteering(SteeringMode.MANUAL, 4)),
            NormalSteering(SteeringMode.AUTO, 4),
        ),
    ],
)
def test_toggle_automatic_assistance_truth_table(
    initial: NormalSteering | MaximumAssistance,
    expected: NormalSteering,
) -> None:
    result = execute_operator_intent(
        ApplicationState(initial), ToggleAutomaticAssistance(), CONFIG
    )

    assert result.state.steering == expected


def test_explicit_maximum_setting_is_idempotent_and_restores_previous_state() -> None:
    initial = ApplicationState(NormalSteering(SteeringMode.MANUAL, 3))

    enabled = execute_operator_intent(initial, SetMaximumAssistance(True), CONFIG).state
    repeated = execute_operator_intent(enabled, SetMaximumAssistance(True), CONFIG).state
    disabled = execute_operator_intent(repeated, SetMaximumAssistance(False), CONFIG).state

    assert repeated == enabled
    assert disabled == initial


def test_exact_manual_level_is_validated_against_server_configuration() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        execute_operator_intent(
            ApplicationState(),
            SetManualAssistanceLevel(11),
            CONFIG,
        )


def test_start_high_beam_strobe_requires_observation_time() -> None:
    with pytest.raises(ValueError, match="observed_at is required"):
        execute_operator_intent(ApplicationState(), StartHighBeamStrobe(), CONFIG)


def test_start_high_beam_strobe_starts_plan_and_asserts_output() -> None:
    strobe_config = HighBeamStrobeConfig(
        cycle_count=3,
        asserted_duration_s=0.15,
        deasserted_duration_s=0.2,
    )

    result = execute_operator_intent(
        ApplicationState(),
        StartHighBeamStrobe(),
        CONFIG,
        OperatorIntentContext(observed_at=12.0),
        high_beam_strobe_config=strobe_config,
    )

    assert result.state.high_beam_enabled is True
    assert result.state.high_beam_strobe_cycles_remaining == 3
    assert result.state.high_beam_next_transition_at == pytest.approx(12.15)
    assert result.effects == (SetHighBeam(True),)


def test_toggle_button_pad_demo_breathe_updates_state_and_projection() -> None:
    enabled = execute_operator_intent(ApplicationState(), ToggleButtonPadDemoBreathe(), CONFIG)
    disabled = execute_operator_intent(enabled.state, ToggleButtonPadDemoBreathe(), CONFIG)

    assert enabled.state.button_pad_demo_breathe_enabled is True
    assert enabled.effects == (SetButtonPadBreathe(DEMO_BREATHE_BUTTON_INDEX, True),)
    assert disabled.state.button_pad_demo_breathe_enabled is False
    assert disabled.effects == (SetButtonPadBreathe(DEMO_BREATHE_BUTTON_INDEX, False),)
