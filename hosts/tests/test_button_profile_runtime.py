from e87canbus.config import SteeringConfig
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.events import ButtonPressed
from e87canbus.domain.intents import SetManualAssistanceLevel, ToggleAutomaticAssistance
from e87canbus.domain.state import SteeringMode
from e87canbus.kernel import (
    ActivateButtonProfile,
    CoordinatorKernel,
    KernelStarted,
    StateTopic,
)


def test_profile_activation_changes_identity_without_pad_program() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    profile = ActiveButtonProfile(
        "custom",
        button_profile_definition_with({5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}),
    )

    commit = kernel.dispatch(ActivateButtonProfile(profile, 3, requested_at=1.0))

    assert commit is not None
    assert commit.snapshot.active_button_profile_id == "custom"
    assert commit.snapshot.active_button_profile_revision == 3
    assert commit.changed_topics == {StateTopic.BUTTONS}
    assert kernel.button_profile.slots[5].colour == (12, 34, 56)


def test_direct_button_input_uses_active_profile_with_no_can_producer() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    profile = ActiveButtonProfile(
        "custom",
        button_profile_definition_with({5: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56))}),
    )
    kernel.dispatch(ActivateButtonProfile(profile, requested_at=1.2))

    assert kernel.dispatch(ButtonPressed(0, 2.0)) is None
    commit = kernel.dispatch(ButtonPressed(5, 2.1))

    assert commit is not None
    assert commit.snapshot.steering_mode is SteeringMode.MANUAL
    assert commit.snapshot.active_button_profile_id == "custom"
    assert commit.state_changed


def test_press_ignores_a_saved_command_rejected_by_current_configuration() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    profile = ActiveButtonProfile(
        "old",
        button_profile_definition_with(
            {
                5: ButtonSlot(
                    SetManualAssistanceLevel(SteeringConfig().manual_level_count),
                    (12, 34, 56),
                )
            }
        ),
    )
    kernel.dispatch(ActivateButtonProfile(profile, requested_at=1.0))

    assert kernel.dispatch(ButtonPressed(5, 2.0)) is None
    assert kernel.snapshot().steering_mode is SteeringMode.AUTO
