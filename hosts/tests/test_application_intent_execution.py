import pytest
from e87canbus.config import SteeringConfig
from e87canbus.domain import controller
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    OperatorIntent,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.state import (
    ApplicationState,
    MaximumAssistance,
    NormalSteering,
    SteeringMode,
)

CONFIG = SteeringConfig(manual_level_count=11)


def execute_operator_intent(
    state: ApplicationState,
    intent: OperatorIntent,
    config: SteeringConfig,
) -> ApplicationState:
    return controller.execute_operator_intent(state, intent, config)


def steering(state: ApplicationState) -> NormalSteering:
    assert isinstance(state.steering, NormalSteering)
    return state.steering


@pytest.mark.parametrize("delta", [-1, 1])
def test_first_adjustment_from_auto_enters_saved_manual_without_adjusting(delta: int) -> None:
    initial = ApplicationState(NormalSteering(SteeringMode.AUTO, 4))

    first = execute_operator_intent(initial, AdjustManualAssistance(delta), CONFIG)
    second = execute_operator_intent(first, AdjustManualAssistance(delta), CONFIG)

    assert steering(first) == NormalSteering(SteeringMode.MANUAL, 4)
    assert steering(second).manual_level == 4 + delta


@pytest.mark.parametrize("delta", [-1, 1])
def test_first_adjustment_from_maximum_restores_saved_manual_without_adjusting(
    delta: int,
) -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.AUTO, 4)))

    first = execute_operator_intent(initial, AdjustManualAssistance(delta), CONFIG)
    second = execute_operator_intent(first, AdjustManualAssistance(delta), CONFIG)

    assert steering(first) == NormalSteering(SteeringMode.MANUAL, 4)
    assert steering(second).manual_level == 4 + delta


def test_exact_manual_selection_clears_maximum_and_sets_requested_level() -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.AUTO, 8)))

    result = execute_operator_intent(
        initial,
        SetManualAssistanceLevel(2),
        CONFIG,
    )

    assert steering(result) == NormalSteering(SteeringMode.MANUAL, 2)


def test_exact_auto_selection_clears_maximum_and_retains_saved_level() -> None:
    initial = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.MANUAL, 8)))

    result = execute_operator_intent(
        initial,
        SelectSteeringMode(SteeringMode.AUTO),
        CONFIG,
    )

    assert steering(result) == NormalSteering(SteeringMode.AUTO, 8)


def test_manual_adjustments_stop_at_configured_level_bounds() -> None:
    low = ApplicationState(NormalSteering(SteeringMode.MANUAL, 0))
    high = ApplicationState(NormalSteering(SteeringMode.MANUAL, 10))

    lowered = execute_operator_intent(low, AdjustManualAssistance(-1), CONFIG)
    raised = execute_operator_intent(high, AdjustManualAssistance(1), CONFIG)

    assert steering(lowered).manual_level == 0
    assert steering(raised).manual_level == 10


def test_toggle_semantics_are_owned_by_the_same_executor() -> None:
    normal = ApplicationState(NormalSteering(SteeringMode.MANUAL, 6))

    automatic = execute_operator_intent(normal, ToggleAutomaticAssistance(), CONFIG)
    maximum = execute_operator_intent(automatic, ToggleMaximumAssistance(), CONFIG)
    restored = execute_operator_intent(maximum, ToggleMaximumAssistance(), CONFIG)

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
    result = execute_operator_intent(ApplicationState(initial), ToggleAutomaticAssistance(), CONFIG)

    assert result.steering == expected


def test_explicit_maximum_setting_is_idempotent_and_restores_previous_state() -> None:
    initial = ApplicationState(NormalSteering(SteeringMode.MANUAL, 3))

    enabled = execute_operator_intent(initial, SetMaximumAssistance(True), CONFIG)
    repeated = execute_operator_intent(enabled, SetMaximumAssistance(True), CONFIG)
    disabled = execute_operator_intent(repeated, SetMaximumAssistance(False), CONFIG)

    assert repeated == enabled
    assert disabled == initial


def test_exact_manual_level_is_validated_against_server_configuration() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        execute_operator_intent(
            ApplicationState(),
            SetManualAssistanceLevel(11),
            CONFIG,
        )
