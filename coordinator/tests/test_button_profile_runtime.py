from dataclasses import replace

import pytest
from e87canbus.adapters.output import EffectRequest
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.domain.button_bindings import (
    ButtonBinding,
    ButtonBindingProfile,
    built_in_button_binding_profile,
)
from e87canbus.domain.controller import (
    SOFT_WHITE,
    button_led_effect,
    derived_button_led_state,
)
from e87canbus.domain.events import RGB_BLUE, RGB_OFF, RGB_WHITE, SetButtonPadProgram
from e87canbus.domain.intents import (
    SetMaximumAssistance,
    ToggleAutomaticAssistance,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance
from e87canbus.kernel import (
    ActivateButtonProfile,
    CoordinatorKernel,
    KernelStarted,
    ReceivedCanFrame,
    StateTopic,
)
from e87canbus.protocol.can import (
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime


def profile(*bindings: ButtonBinding, profile_id: str = "user") -> ButtonBindingProfile:
    return ButtonBindingProfile(profile_id, bindings)


def test_derived_led_presentation_follows_binding_intents_not_fixed_indexes() -> None:
    selected = profile(
        ButtonBinding(7, ToggleAutomaticAssistance()),
        ButtonBinding(12, SetMaximumAssistance(True)),
    )

    normal = derived_button_led_state(ApplicationState(), selected)
    maximum = derived_button_led_state(
        replace(
            ApplicationState(),
            steering=MaximumAssistance(ApplicationState().steering),
        ),
        selected,
    )

    assert normal.rgb[7] == RGB_BLUE
    assert normal.rgb[12] == SOFT_WHITE
    assert normal.rgb[0] == RGB_OFF
    assert maximum.rgb[12] == RGB_WHITE


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
    selected = profile(ButtonBinding(9, ToggleAutomaticAssistance()))

    commit = kernel.dispatch(
        ActivateButtonProfile(selected, saved_profile_revision=3, requested_at=1.0)
    )

    assert commit is not None
    assert commit.changed_topics == frozenset({StateTopic.BUTTONS})
    assert commit.state_changed is True
    assert commit.effects == (
        EffectRequest(button_led_effect(ApplicationState(), False, profile=selected)),
    )
    assert commit.snapshot.button_pad_program == commit.effects[0].effect.program
    assert commit.snapshot != previous_snapshot


def test_activation_rolls_back_routing_when_led_presentation_fails() -> None:
    original = built_in_button_binding_profile()

    def presenter(state, selected, servotronic_usable):
        if selected.profile_id == "broken":
            raise RuntimeError("presentation failed")
        return derived_button_led_state(state, selected, servotronic_usable)

    kernel = CoordinatorKernel(button_led_presenter=presenter)
    kernel.dispatch(KernelStarted(0.0))

    with pytest.raises(RuntimeError, match="presentation failed"):
        kernel.dispatch(
            ActivateButtonProfile(
                profile(
                    ButtonBinding(9, ToggleAutomaticAssistance()),
                    profile_id="broken",
                ),
                requested_at=1.0,
            )
        )

    unchanged = kernel.dispatch(ActivateButtonProfile(original, requested_at=2.0))
    assert unchanged is not None
    assert unchanged.state_changed is False
    assert unchanged.changed_topics == frozenset()


def test_profile_without_demo_binding_cannot_start_a_demo_led_track() -> None:
    state = replace(ApplicationState(), button_pad_demo_breathe_enabled=True)
    selected = profile(ButtonBinding(2, ToggleAutomaticAssistance()))

    effect = button_led_effect(state, profile=selected)

    assert isinstance(effect, SetButtonPadProgram)
    assert effect == button_led_effect(
        replace(state, button_pad_demo_breathe_enabled=False), profile=selected
    )


def test_initial_profile_drives_startup_snapshot_and_device_sync_effect() -> None:
    selected = profile(ButtonBinding(11, ToggleAutomaticAssistance()))
    kernel = CoordinatorKernel()
    kernel.configure_initial_button_profile(selected, 4)

    commit = kernel.dispatch(KernelStarted(0.0))

    assert commit is not None
    expected = button_led_effect(ApplicationState(), False, profile=selected)
    assert commit.snapshot.button_pad_program == expected.program
    assert kernel.button_binding_profile == selected
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
    selected = profile(ButtonBinding(6, ToggleAutomaticAssistance()))
    runtime = SimulatedControllerRuntime()
    runtime.configure_initial_button_profile(selected, 7)

    runtime.start()

    assert runtime.kernel.button_binding_profile == selected
    assert runtime.kernel.button_profile_saved_revision == 7
