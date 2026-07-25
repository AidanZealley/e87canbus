from dataclasses import FrozenInstanceError

import pytest
from e87canbus.config import HighBeamStrobeConfig
from e87canbus.domain.buttons.profiles import (
    BUTTON_PROFILE_SCHEMA_VERSION,
    ActiveButtonProfile,
    ButtonProfileDefinition,
    built_in_active_button_profile,
    button_profile_definition_with,
    empty_button_profile_definition,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    OperatorIntentContext,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
    intent_requires_servotronic,
)
from e87canbus.domain.state import SteeringMode


def test_exact_steering_intents_validate_their_values() -> None:
    assert SetManualAssistanceLevel(0).level == 0
    assert SetMaximumAssistance(False).enabled is False

    with pytest.raises(ValueError, match="supported SteeringMode"):
        SelectSteeringMode("manual")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative integer"):
        SetManualAssistanceLevel(-1)
    with pytest.raises(ValueError, match="boolean"):
        SetMaximumAssistance(1)  # type: ignore[arg-type]


@pytest.mark.parametrize("delta", [-2, 0, 2, 1.0, True])
def test_adjust_manual_assistance_requires_one_stage_delta(delta: object) -> None:
    with pytest.raises(ValueError, match="-1 or 1"):
        AdjustManualAssistance(delta)  # type: ignore[arg-type]


def test_operator_intents_are_immutable_values() -> None:
    intent = AdjustManualAssistance(1)
    with pytest.raises(FrozenInstanceError):
        intent.delta = -1  # type: ignore[misc]


@pytest.mark.parametrize("observed_at", [-0.1, float("inf"), float("nan"), True, "now"])
def test_intent_context_requires_a_finite_non_negative_observation_time(
    observed_at: object,
) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        OperatorIntentContext(observed_at=observed_at)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "intent",
    [
        SelectSteeringMode(SteeringMode.AUTO),
        ToggleAutomaticAssistance(),
        AdjustManualAssistance(1),
        SetMaximumAssistance(True),
        ToggleMaximumAssistance(),
    ],
)
def test_steering_intents_require_servotronic(intent: object) -> None:
    assert intent_requires_servotronic(intent) is True  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "intent",
    [StartHighBeamStrobe()],
)
def test_non_steering_intents_do_not_require_servotronic(intent: object) -> None:
    assert intent_requires_servotronic(intent) is False  # type: ignore[arg-type]


def test_built_in_profile_describes_the_existing_fixed_mapping() -> None:
    profile = built_in_active_button_profile()

    assert profile.intent_for_press(0) == ToggleAutomaticAssistance()
    assert profile.intent_for_press(1) == AdjustManualAssistance(-1)
    assert profile.intent_for_press(2) == AdjustManualAssistance(1)
    assert profile.intent_for_press(3) == ToggleMaximumAssistance()
    assert profile.intent_for_press(4) == StartHighBeamStrobe()
    assert profile.intent_for_press(5) is None
    assert profile.intent_for_press(15) is None


def test_built_in_profile_uses_the_configured_high_beam_button() -> None:
    profile = built_in_active_button_profile(HighBeamStrobeConfig(button_index=7))

    assert profile.intent_for_press(7) == StartHighBeamStrobe()
    assert profile.intent_for_press(4) is None


def test_profile_rejects_out_of_range_or_unassignable_slots() -> None:
    with pytest.raises(ValueError, match="between 0 and 15"):
        button_profile_definition_with({16: ToggleAutomaticAssistance()})
    with pytest.raises(ValueError, match="not user-bindable"):
        button_profile_definition_with({1: object()})  # type: ignore[dict-item]


def test_profile_rejects_a_definition_that_is_not_a_full_slot_set() -> None:
    with pytest.raises(ValueError, match="16-entry tuple"):
        ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, (None, None))
    with pytest.raises(ValueError, match="16-entry tuple"):
        ButtonProfileDefinition(BUTTON_PROFILE_SCHEMA_VERSION, [None] * 16)  # type: ignore[arg-type]


def test_profile_rejects_a_definition_of_the_wrong_type() -> None:
    with pytest.raises(TypeError, match="must be a ButtonProfileDefinition"):
        ActiveButtonProfile("malformed", object())  # type: ignore[arg-type]


@pytest.mark.parametrize("profile_id", ["", " padded "])
def test_profile_requires_a_stable_trimmed_identifier(profile_id: str) -> None:
    with pytest.raises(ValueError, match="non-empty trimmed"):
        ActiveButtonProfile(profile_id, empty_button_profile_definition())


def test_profile_identifier_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="profile_id must be a string"):
        ActiveButtonProfile(1, empty_button_profile_definition())  # type: ignore[arg-type]
