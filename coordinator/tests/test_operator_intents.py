from dataclasses import FrozenInstanceError

import pytest
from e87canbus.application.button_bindings import (
    ButtonBinding,
    ButtonBindingProfile,
    built_in_button_binding_profile,
)
from e87canbus.application.intents import (
    AdjustManualAssistance,
    IntentDispatcher,
    OperatorIntentContext,
    SelectSteeringMode,
    SetMaximumAssistance,
    StartHighBeamStrobe,
    ToggleButtonPadDemoBreathe,
    ToggleMaximumAssistance,
    ToggleSteeringMode,
    intent_requires_servotronic,
)
from e87canbus.application.state import SteeringMode
from e87canbus.config import HighBeamStrobeConfig


def test_exact_steering_intents_validate_their_values() -> None:
    assert SelectSteeringMode(SteeringMode.MANUAL, 0).manual_level == 0
    assert SetMaximumAssistance(False).enabled is False

    with pytest.raises(ValueError, match="supported SteeringMode"):
        SelectSteeringMode("manual")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative integer"):
        SelectSteeringMode(SteeringMode.MANUAL, -1)
    with pytest.raises(ValueError, match="boolean"):
        SetMaximumAssistance(1)  # type: ignore[arg-type]


@pytest.mark.parametrize("delta", [0, 1.0, True])
def test_adjust_manual_assistance_requires_a_nonzero_integer(delta: object) -> None:
    with pytest.raises(ValueError, match="non-zero integer"):
        AdjustManualAssistance(delta)  # type: ignore[arg-type]


def test_operator_intents_are_immutable_values() -> None:
    intent = AdjustManualAssistance(1)
    with pytest.raises(FrozenInstanceError):
        intent.delta = -1  # type: ignore[misc]


def test_dispatcher_forwards_supported_intent_to_one_executor() -> None:
    received: list[object] = []
    dispatcher = IntentDispatcher(
        lambda intent, context: received.append((intent, context)) or "handled"
    )
    intent = ToggleMaximumAssistance()
    context = OperatorIntentContext(observed_at=12.5)

    assert dispatcher.dispatch(intent, context) == "handled"
    assert received == [(intent, context)]


def test_dispatcher_supplies_empty_context_for_non_timed_intents() -> None:
    received: list[OperatorIntentContext] = []
    dispatcher = IntentDispatcher(lambda intent, context: received.append(context))

    dispatcher.dispatch(ToggleSteeringMode())

    assert received == [OperatorIntentContext()]


@pytest.mark.parametrize("observed_at", [-0.1, float("inf"), float("nan"), True, "now"])
def test_intent_context_requires_a_finite_non_negative_observation_time(
    observed_at: object,
) -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        OperatorIntentContext(observed_at=observed_at)  # type: ignore[arg-type]


def test_dispatcher_rejects_values_outside_the_closed_intent_set() -> None:
    dispatcher = IntentDispatcher(lambda intent, context: intent)

    with pytest.raises(TypeError, match="unsupported operator intent"):
        dispatcher.dispatch(object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="OperatorIntentContext"):
        dispatcher.dispatch(ToggleSteeringMode(), object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "intent",
    [
        SelectSteeringMode(SteeringMode.AUTO),
        ToggleSteeringMode(),
        AdjustManualAssistance(1),
        SetMaximumAssistance(True),
        ToggleMaximumAssistance(),
    ],
)
def test_steering_intents_require_servotronic(intent: object) -> None:
    assert intent_requires_servotronic(intent) is True  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "intent",
    [StartHighBeamStrobe(), ToggleButtonPadDemoBreathe()],
)
def test_non_steering_intents_do_not_require_servotronic(intent: object) -> None:
    assert intent_requires_servotronic(intent) is False  # type: ignore[arg-type]


def test_built_in_profile_describes_the_existing_fixed_mapping() -> None:
    profile = built_in_button_binding_profile()

    assert profile.intent_for_press(0) == ToggleSteeringMode()
    assert profile.intent_for_press(1) == AdjustManualAssistance(-1)
    assert profile.intent_for_press(2) == AdjustManualAssistance(1)
    assert profile.intent_for_press(3) == ToggleMaximumAssistance()
    assert profile.intent_for_press(4) == StartHighBeamStrobe()
    assert profile.intent_for_press(15) == ToggleButtonPadDemoBreathe()
    assert profile.intent_for_press(5) is None


def test_built_in_profile_uses_the_configured_high_beam_button() -> None:
    profile = built_in_button_binding_profile(HighBeamStrobeConfig(button_index=7))

    assert profile.intent_for_press(7) == StartHighBeamStrobe()
    assert profile.intent_for_press(4) is None


def test_profile_rejects_duplicate_or_out_of_range_buttons() -> None:
    binding = ButtonBinding(0, ToggleSteeringMode())

    with pytest.raises(ValueError, match="same button"):
        ButtonBindingProfile("duplicate", (binding, binding))
    with pytest.raises(ValueError, match="between 0 and 15"):
        ButtonBinding(16, ToggleSteeringMode())
    with pytest.raises(TypeError, match="supported operator intent"):
        ButtonBinding(1, object())  # type: ignore[arg-type]


def test_profile_rejects_mutable_or_malformed_bindings() -> None:
    binding = ButtonBinding(0, ToggleSteeringMode())

    with pytest.raises(TypeError, match="immutable tuple"):
        ButtonBindingProfile("mutable", [binding])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="only ButtonBinding"):
        ButtonBindingProfile("malformed", (object(),))  # type: ignore[arg-type]


@pytest.mark.parametrize("profile_id", ["", " padded "])
def test_profile_requires_a_stable_trimmed_identifier(profile_id: str) -> None:
    with pytest.raises(ValueError, match="non-empty trimmed"):
        ButtonBindingProfile(profile_id, ())


def test_profile_identifier_must_be_a_string() -> None:
    with pytest.raises(TypeError, match="profile_id must be a string"):
        ButtonBindingProfile(1, ())  # type: ignore[arg-type]
