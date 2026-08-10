from dataclasses import replace

import pytest
from e87canbus.adapters.output import EffectRequest
from e87canbus.config import CanNetwork, CustomCanIds, SteeringConfig
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    ButtonCommand,
    ButtonSlot,
    built_in_active_button_profile,
    button_profile_definition_with,
)
from e87canbus.domain.controller import (
    ButtonLedProjection,
    derived_button_led_state,
)
from e87canbus.domain.devices.catalogue import DeviceRole
from e87canbus.domain.events import (
    SetButtonPadProgram,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    ToggleAutomaticAssistance,
)
from e87canbus.domain.state import (
    BUTTON_FEEDBACK_REJECTED,
    RGB_WHITE,
    ApplicationState,
    ButtonFeedback,
    ButtonVisual,
    MaximumAssistance,
    SteeringMode,
)
from e87canbus.kernel import (
    ActivateButtonProfile,
    CoordinatorKernel,
    KernelStarted,
    ReceivedCanFrame,
    StateTopic,
)
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime


def profile(assignments: dict[int, ButtonCommand], profile_id: str = "user") -> ActiveButtonProfile:
    """Bind commands to buttons; these cases are about routing, not authored colour."""

    return ActiveButtonProfile(
        profile_id,
        button_profile_definition_with(
            {index: ButtonSlot(command, RGB_WHITE) for index, command in assignments.items()}
        ),
    )


def led_effect(
    state: ApplicationState,
    selected: ActiveButtonProfile,
    servotronic_usable: bool = True,
) -> SetButtonPadProgram:
    return ButtonLedProjection(selected, servotronic_usable).effect(state)


def activate_devices(kernel: CoordinatorKernel) -> None:
    """Bring the pad and the Servotronic controller through their real handshake."""

    ids = CustomCanIds()
    for hello_id, heartbeat_id in (
        (ids.button_pad_hello, ids.button_pad_heartbeat),
        (ids.servotronic_controller_hello, ids.servotronic_controller_heartbeat),
    ):
        kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN, encode_hello(DeviceHelloPayload(1, 1, 1, 0), hello_id), 0.1
            )
        )
        kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                encode_heartbeat(
                    DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                    heartbeat_id,
                ),
                0.2,
            )
        )
    assert kernel.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).status.value == "active"


def press_button(kernel: CoordinatorKernel, button_index: int) -> None:
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, bytes((button_index, 1))),
            2.0,
        )
    )


def test_derived_led_presentation_follows_binding_intents_not_fixed_indexes() -> None:
    selected = profile({7: ToggleAutomaticAssistance(), 12: SetMaximumAssistance(True)})

    normal = derived_button_led_state(ApplicationState(), selected)
    maximum = derived_button_led_state(
        replace(
            ApplicationState(),
            steering=MaximumAssistance(ApplicationState().steering),
        ),
        selected,
    )

    assert normal.visuals[7] is ButtonVisual.ACTIVE
    assert normal.visuals[12] is ButtonVisual.INACTIVE
    assert normal.visuals[0] is ButtonVisual.UNASSIGNED
    assert maximum.visuals[12] is ButtonVisual.ACTIVE


def test_activation_replaces_profile_and_emits_complete_led_program() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    previous_snapshot = kernel.snapshot()
    ids = CustomCanIds()
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, 1, 0), ids.button_pad_hello),
            0.1,
        )
    )
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                ids.button_pad_heartbeat,
            ),
            0.2,
        )
    )
    selected = profile({9: ToggleAutomaticAssistance()})

    commit = kernel.dispatch(
        ActivateButtonProfile(selected, saved_profile_revision=3, requested_at=1.0)
    )

    assert commit is not None
    assert commit.changed_topics == frozenset({StateTopic.BUTTONS})
    assert commit.state_changed is True
    assert commit.effects == (
        EffectRequest(led_effect(ApplicationState(), selected, servotronic_usable=False)),
    )
    assert commit.snapshot.button_pad_program == commit.effects[0].effect.program
    assert commit.snapshot != previous_snapshot

    repeated = kernel.dispatch(
        ActivateButtonProfile(selected, saved_profile_revision=3, requested_at=2.0)
    )

    # Re-activating the profile already in force must not retransmit the program.
    assert repeated is not None
    assert repeated.effects == ()
    assert repeated.changed_topics == frozenset()
    assert repeated.state_changed is False


def test_activation_rolls_back_routing_when_led_presentation_fails() -> None:
    original = built_in_active_button_profile()

    def presenter(state, selected, servotronic_usable):
        if selected.profile_id == "broken":
            raise RuntimeError("presentation failed")
        return derived_button_led_state(state, selected, servotronic_usable)

    kernel = CoordinatorKernel(button_led_presenter=presenter)
    kernel.dispatch(KernelStarted(0.0))

    with pytest.raises(RuntimeError, match="presentation failed"):
        kernel.dispatch(
            ActivateButtonProfile(
                profile({9: ToggleAutomaticAssistance()}, profile_id="broken"),
                requested_at=1.0,
            )
        )

    unchanged = kernel.dispatch(ActivateButtonProfile(original, requested_at=2.0))
    assert unchanged is not None
    assert unchanged.state_changed is False
    assert unchanged.changed_topics == frozenset()


def test_visible_press_on_a_user_bound_button_is_not_confirmed_by_a_blink() -> None:
    # The built-in profile binds nothing to button 7, so a profile-blind comparison
    # sees an unassigned button on both sides and blinks over a real change.
    kernel = CoordinatorKernel(button_profile=profile({7: ToggleAutomaticAssistance()}))
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    press_button(kernel, 7)

    assert kernel.snapshot().steering_mode is SteeringMode.MANUAL
    assert kernel.state.button_feedback[7] is None


def test_invisible_press_is_confirmed_even_where_the_built_in_profile_would_change() -> None:
    # Button 0 is ToggleAutomaticAssistance built in, so a profile-blind comparison
    # reads the steering-mode change as visible and swallows the confirmation. The
    # flash carries this profile's authored colour, which ``profile`` makes white.
    kernel = CoordinatorKernel(button_profile=profile({0: AdjustManualAssistance(1)}))
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    press_button(kernel, 0)

    assert kernel.snapshot().steering_mode is SteeringMode.MANUAL
    assert kernel.state.button_feedback[0] == ButtonFeedback(RGB_WHITE, 1)


def test_initial_profile_drives_startup_snapshot_and_device_sync_effect() -> None:
    selected = profile({11: ToggleAutomaticAssistance()})
    kernel = CoordinatorKernel()
    kernel.configure_initial_button_profile(selected, 4)

    commit = kernel.dispatch(KernelStarted(0.0))

    assert commit is not None
    expected = led_effect(ApplicationState(), selected, servotronic_usable=False)
    assert commit.snapshot.button_pad_program == expected.program
    assert kernel.button_profile == selected
    assert kernel.button_profile_saved_revision == 4

    ids = CustomCanIds()
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, 1, 0), ids.button_pad_hello),
            0.1,
        )
    )
    synced = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                ids.button_pad_heartbeat,
            ),
            0.2,
        )
    )
    assert synced is not None
    assert EffectRequest(expected) in synced.effects


def test_simulation_preserves_initial_saved_profile_revision() -> None:
    selected = profile({6: ToggleAutomaticAssistance()})
    runtime = SimulatedControllerRuntime()
    runtime.configure_initial_button_profile(selected, 7)

    runtime.start()

    assert runtime.kernel.button_profile == selected
    assert runtime.kernel.button_profile_saved_revision == 7


def test_press_of_a_command_the_configuration_rejects_fails_as_feedback() -> None:
    """A profile stored before a configuration change must not raise out of the kernel."""

    stage_count = SteeringConfig().manual_level_count
    kernel = CoordinatorKernel(
        button_profile=profile({5: SetManualAssistanceLevel(stage_count)}),
    )
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    commit = kernel.dispatch(
        ReceivedCanFrame(CanNetwork.KCAN, CanFrame(CustomCanIds().button_event, bytes((5, 1))), 2.0)
    )

    assert commit is not None
    assert kernel.state.button_feedback[5] == BUTTON_FEEDBACK_REJECTED
