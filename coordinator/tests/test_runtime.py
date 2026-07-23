import logging

import pytest
from e87canbus.adapters.output import EffectRequest
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.domain.button_bindings import ButtonBinding, ButtonBindingProfile
from e87canbus.domain.button_pad import static_button_pad_program
from e87canbus.domain.controller import SOFT_WHITE
from e87canbus.domain.device import DeviceRole
from e87canbus.domain.device_registry import FeatureUnavailable
from e87canbus.domain.events import (
    RGB_AMBER,
    RGB_BLUE,
    RGB_OFF,
    RGB_WHITE,
    ApplicationEvent,
    ButtonLedState,
    ButtonPressed,
    SetButtonPadProgram,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    TriggerButtonPadBlink,
)
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    SetMaximumAssistance,
    ToggleAutomaticAssistance,
)
from e87canbus.domain.state import SpeedSample, SteeringMode
from e87canbus.kernel import (
    INITIAL_KERNEL_TOPICS,
    CanEffectExecutionFailed,
    CanReaderFailed,
    CoordinatorKernel,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelLifecycle,
    KernelStarted,
    ReceivedCanFrame,
    RuntimeFault,
    RuntimeFaultKind,
    RuntimeHealth,
    ShutdownRequested,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    RoutedCanFrame,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runners.simulation.protocol import SimulationProtocolRouter, encode_simulated_speed


def led_program(leds: ButtonLedState) -> SetButtonPadProgram:
    return SetButtonPadProgram(static_button_pad_program(leds.rgb))


RESTING_LEDS = (
    (
        RGB_OFF,
        SOFT_WHITE,
        SOFT_WHITE,
        SOFT_WHITE,
        SOFT_WHITE,
    )
    + (RGB_OFF,) * 10
    + (SOFT_WHITE,)
)
AUTO_LEDS = ButtonLedState((RGB_BLUE,) + RESTING_LEDS[1:])
MANUAL_LEDS = ButtonLedState((RGB_AMBER,) + RESTING_LEDS[1:])
MAXIMUM_LEDS = ButtonLedState((RGB_AMBER, SOFT_WHITE, SOFT_WHITE, RGB_WHITE) + RESTING_LEDS[4:])


def activate_devices(kernel: CoordinatorKernel) -> None:
    ids = CustomCanIds()
    for role, hello_id, heartbeat_id in (
        (DeviceRole.BUTTON_PAD, ids.button_pad_hello, ids.button_pad_heartbeat),
        (
            DeviceRole.SERVOTRONIC_CONTROLLER,
            ids.servotronic_controller_hello,
            ids.servotronic_controller_heartbeat,
        ),
    ):
        del role
        kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                encode_hello(DeviceHelloPayload(1, 1, 1, 0), hello_id),
                1.0,
            )
        )
        kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                encode_heartbeat(
                    DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                    heartbeat_id,
                ),
                1.1,
            )
        )


def press_button(kernel: CoordinatorKernel, button_index: int, observed_at: float = 2.0):
    return kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, bytes((button_index, 1))),
            observed_at,
        )
    )


def steering_effects(commit) -> tuple[SetSteeringAssistance, ...]:
    """Exclude button acknowledgement/presentation when comparing input origins."""

    return tuple(
        request.effect
        for request in commit.effects
        if isinstance(request.effect, SetSteeringAssistance)
    )


def steering_projection(commit) -> tuple[SteeringMode, int, int, bool]:
    snapshot = commit.snapshot
    return (
        snapshot.steering_mode,
        snapshot.manual_assistance_level,
        snapshot.manual_assistance_level_count,
        snapshot.maximum_assistance_active,
    )


def test_non_network_inbox_overflow_is_fatal() -> None:
    fault = RuntimeFault(RuntimeFaultKind.INBOX_OVERFLOW, 1.0, "command inbox full")

    health = RuntimeHealth().with_inbox_overflow(None, fault)

    assert health.fatal is True
    assert health.inbox_overflow_fault == fault
    assert all(network.fault is None for network in health.networks)


class SpeedRouter(ProtocolRouter):
    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | None:
        return SpeedObserved(SpeedSample(float(routed.frame.data[0]), observed_at, routed.network))


def test_protocol_router_discards_releases_and_scopes_button_decode_to_kcan() -> None:
    ids = CustomCanIds()
    router = ProtocolRouter(ids)
    pressed = CanFrame(ids.button_event, b"\x00\x01")
    released = CanFrame(ids.button_event, b"\x00\x00")

    assert router.decode(RoutedCanFrame(CanNetwork.PTCAN, pressed), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.FCAN, pressed), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, released), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, pressed), 1.0) == ButtonPressed(0, 1.0)


@pytest.mark.parametrize("button_index", [-1, 16, True])
def test_button_pressed_rejects_invalid_led_indexes(button_index: object) -> None:
    with pytest.raises(ValueError, match="button press index"):
        ButtonPressed(button_index)  # type: ignore[arg-type]


def test_mixed_inputs_produce_deterministic_revisions_snapshots_and_effects() -> None:
    inputs = (
        KernelStarted(0.0),
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            0.1,
        ),
        TimerElapsed(0.2),
    )
    first = CoordinatorKernel()
    second = CoordinatorKernel()

    first_commits = tuple(first.dispatch(kernel_input) for kernel_input in inputs)
    second_commits = tuple(second.dispatch(kernel_input) for kernel_input in inputs)

    assert first_commits == second_commits
    assert [commit.revision for commit in first_commits if commit is not None] == [1, 2]
    assert first_commits[0] is not None
    assert first_commits[0].changed_topics == INITIAL_KERNEL_TOPICS
    assert first_commits[0].effects == ()
    assert first_commits[1] is None
    assert first_commits[2] is not None
    assert first_commits[2].effects == ()
    assert first_commits[2].changed_topics == frozenset()
    assert first_commits[2].state_changed is False


def test_decoded_physical_button_press_uses_the_injected_profile() -> None:
    profile = ButtonBindingProfile(
        "test-remap",
        (ButtonBinding(8, ToggleAutomaticAssistance()),),
    )
    kernel = CoordinatorKernel(button_binding_profile=profile)
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    unbound = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            1.0,
        )
    )
    remapped = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x08\x01"),
            2.0,
        )
    )

    assert unbound is not None
    assert unbound.snapshot.steering_mode is SteeringMode.AUTO
    assert all(request.origin_button_index is None for request in unbound.effects)
    assert remapped is not None
    assert remapped.snapshot.steering_mode is SteeringMode.MANUAL
    assert all(request.origin_button_index == 8 for request in remapped.effects)


def test_semantic_set_inputs_are_repeat_safe_with_exact_topics_and_effects() -> None:
    kernel = CoordinatorKernel()
    assert kernel.dispatch(KernelStarted(0.0)) is not None
    activate_devices(kernel)

    maximum = kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))
    repeated_maximum = kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))
    manual = kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(4)))
    repeated_manual = kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(4)))
    normal = kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(False)))
    repeated_normal = kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(False)))
    auto = kernel.dispatch(ExecuteOperatorIntent(SelectSteeringMode(SteeringMode.AUTO)))
    repeated_auto = kernel.dispatch(ExecuteOperatorIntent(SelectSteeringMode(SteeringMode.AUTO)))

    assert maximum is not None
    assert maximum.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert maximum.effects == (
        EffectRequest(led_program(MAXIMUM_LEDS)),
        EffectRequest(SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM)),
    )
    assert maximum.snapshot.maximum_assistance_active is True

    for repeated in (
        repeated_maximum,
        repeated_manual,
        repeated_normal,
        repeated_auto,
    ):
        assert repeated is not None
        assert repeated.changed_topics == frozenset()
        assert repeated.effects == ()
        assert repeated.state_changed is False

    assert manual is not None
    assert manual.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert manual.effects == (
        EffectRequest(led_program(MANUAL_LEDS)),
        EffectRequest(SetSteeringAssistance(0.4, SteeringCommandReason.MANUAL)),
    )
    assert manual.snapshot.steering_mode is SteeringMode.MANUAL
    assert manual.snapshot.manual_assistance_level == 4
    assert manual.snapshot.maximum_assistance_active is False

    assert normal is not None
    assert normal.changed_topics == frozenset()
    assert normal.effects == ()
    assert normal.state_changed is False

    assert auto is not None
    assert auto.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert auto.effects == (
        EffectRequest(led_program(AUTO_LEDS)),
        EffectRequest(SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED)),
    )
    assert auto.snapshot.steering_mode is SteeringMode.AUTO
    assert auto.snapshot.manual_assistance_level == 4


@pytest.mark.parametrize("button_index", [1, 2])
def test_button_and_relative_manual_command_clear_maximum_with_equivalent_outputs(
    button_index: int,
) -> None:
    button_kernel = CoordinatorKernel()
    command_kernel = CoordinatorKernel()
    for kernel in (button_kernel, command_kernel):
        kernel.dispatch(KernelStarted(0.0))
        activate_devices(kernel)
        kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(4)))
        kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))

    button = press_button(button_kernel, button_index)
    delta = -1 if button_index == 1 else 1
    command = command_kernel.dispatch(ExecuteOperatorIntent(AdjustManualAssistance(delta)))

    assert button is not None and command is not None
    assert steering_projection(button) == steering_projection(command)
    assert button.changed_topics == command.changed_topics
    assert (
        steering_effects(button)
        == steering_effects(command)
        == (SetSteeringAssistance(0.4, SteeringCommandReason.MANUAL),)
    )
    assert all(request.origin_button_index == button_index for request in button.effects)
    assert all(request.origin_button_index is None for request in command.effects)


@pytest.mark.parametrize("button_index", [1, 2])
def test_button_and_relative_command_enter_manual_at_remembered_level(button_index: int) -> None:
    button_kernel = CoordinatorKernel()
    command_kernel = CoordinatorKernel()
    for kernel in (button_kernel, command_kernel):
        kernel.dispatch(KernelStarted(0.0))
        activate_devices(kernel)
        kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(7)))
        kernel.dispatch(ExecuteOperatorIntent(SelectSteeringMode(SteeringMode.AUTO)))

    button = press_button(button_kernel, button_index)
    delta = -1 if button_index == 1 else 1
    command = command_kernel.dispatch(ExecuteOperatorIntent(AdjustManualAssistance(delta)))

    assert button is not None and command is not None
    # Button acknowledgement is intentionally part of the button program only;
    # authoritative steering and actuator output must still converge.
    assert steering_projection(button) == steering_projection(command)
    assert button.snapshot.manual_assistance_level == 7
    assert (
        steering_effects(button)
        == steering_effects(command)
        == (SetSteeringAssistance(0.7, SteeringCommandReason.MANUAL),)
    )


def test_maximum_toggle_button_matches_explicit_enable_and_disable_commands() -> None:
    button_kernel = CoordinatorKernel()
    command_kernel = CoordinatorKernel()
    for kernel in (button_kernel, command_kernel):
        kernel.dispatch(KernelStarted(0.0))
        activate_devices(kernel)
        kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(3)))

    button_enabled = press_button(button_kernel, 3, 2.0)
    command_enabled = command_kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))
    assert button_enabled is not None and command_enabled is not None
    assert steering_projection(button_enabled) == steering_projection(command_enabled)
    assert steering_effects(button_enabled) == steering_effects(command_enabled)

    button_disabled = press_button(button_kernel, 3, 3.0)
    command_disabled = command_kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(False)))
    assert button_disabled is not None and command_disabled is not None
    assert steering_projection(button_disabled) == steering_projection(command_disabled)
    assert steering_effects(button_disabled) == steering_effects(command_disabled)


def test_maximum_snapshot_preserves_remembered_manual_level_and_effective_override() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)
    kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(4)))

    maximum = kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))

    assert maximum is not None
    assert maximum.snapshot.manual_assistance_level == 4
    assert maximum.snapshot.maximum_assistance_active is True
    assert steering_effects(maximum) == (SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM),)


def test_projected_eleven_levels_and_button_bounds_match_exact_commands() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    assert kernel.snapshot().manual_assistance_level_count == 11
    kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(0)))
    low = press_button(kernel, 1, 2.0)
    assert low is not None and low.snapshot.manual_assistance_level == 0
    kernel.dispatch(ExecuteOperatorIntent(SetManualAssistanceLevel(10)))
    high = press_button(kernel, 2, 3.0)
    assert high is not None and high.snapshot.manual_assistance_level == 10


def test_unavailable_servotronic_rejects_both_origins_with_button_only_feedback() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    ids = CustomCanIds()
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, 1, 0), ids.button_pad_hello),
            1.0,
        )
    )
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                ids.button_pad_heartbeat,
            ),
            1.1,
        )
    )
    before = kernel.snapshot()

    with pytest.raises(FeatureUnavailable):
        kernel.dispatch(ExecuteOperatorIntent(SelectSteeringMode(SteeringMode.MANUAL)))
    rejected_button = press_button(kernel, 2)

    assert rejected_button is not None
    assert rejected_button.snapshot.steering_mode is before.steering_mode
    assert rejected_button.snapshot.manual_assistance_level == before.manual_assistance_level
    assert steering_effects(rejected_button) == ()
    assert any(
        isinstance(request.effect, TriggerButtonPadBlink) and request.effect.colour.value == "amber"
        for request in rejected_button.effects
    )


def test_unknown_and_malformed_frames_create_no_commits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    with caplog.at_level(logging.WARNING):
        unknown = kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, CanFrame(0x123, b"\x00"), 1.0))
        malformed = kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                CanFrame(ids.button_event, b"\x00"),
                2.0,
            )
        )

    assert unknown is None
    assert malformed is None
    assert kernel.diagnostics().revision == 1
    network = kernel.diagnostics().health.for_network(CanNetwork.KCAN)
    assert network.received_frames == 2
    assert (network.ignored_frames, network.malformed_frames) == (1, 1)
    assert "ignored malformed recognized frame" in caplog.text


def test_out_of_range_button_can_payload_is_counted_as_malformed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    with caplog.at_level(logging.WARNING):
        commit = kernel.dispatch(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                CanFrame(ids.button_event, b"\x10\x01"),
                1.0,
            )
        )

    assert commit is None
    assert kernel.diagnostics().revision == 1
    network = kernel.diagnostics().health.for_network(CanNetwork.KCAN)
    assert network.received_frames == 1
    assert (network.ignored_frames, network.malformed_frames) == (0, 1)
    assert "button event index must be between 0 and 15" in caplog.text


def test_button_topic_is_backed_by_one_complete_immutable_led_projection() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    commit = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            0.1,
        )
    )

    assert commit is not None
    led_effects = tuple(
        effect.effect for effect in commit.effects if isinstance(effect.effect, SetButtonPadProgram)
    )
    assert commit.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert led_effects == (led_program(MANUAL_LEDS),)
    assert all(isinstance(payload, bytes) for payload in led_effects[0].program.payloads)
    assert all(len(payload) == 16 for payload in led_effects[0].program.payloads)


@pytest.mark.parametrize(
    ("kernel_input", "kind", "fallback_reason"),
    [
        (
            CanReaderFailed(CanNetwork.FCAN, 1.0, "reader"),
            RuntimeFaultKind.CAN_READER,
            SteeringCommandReason.CAN_READER_FAILURE,
        ),
        (
            CanEffectExecutionFailed(CanNetwork.KCAN, 2.0, "effect"),
            RuntimeFaultKind.CAN_EFFECT_EXECUTION,
            None,
        ),
        (
            InboxOverflowed(CanNetwork.PTCAN, 3.0, "overflow"),
            RuntimeFaultKind.INBOX_OVERFLOW,
            SteeringCommandReason.INBOX_OVERFLOW,
        ),
    ],
)
def test_fault_inputs_are_visible_in_immutable_runtime_health(
    kernel_input: CanReaderFailed | CanEffectExecutionFailed | InboxOverflowed,
    kind: RuntimeFaultKind,
    fallback_reason: SteeringCommandReason | None,
) -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    commit = kernel.dispatch(kernel_input)

    assert kernel_input.network is not None
    fault = kernel.health.for_network(kernel_input.network).fault
    assert fault is not None
    assert fault.kind is kind
    assert kernel.health.fatal is True
    assert commit is not None
    assert commit.changed_topics == {StateTopic.HEALTH}
    if fallback_reason is not None:
        assert commit.effects == (EffectRequest(SetSteeringAssistance(0.0, fallback_reason)),)
    else:
        assert commit.effects == ()


def test_steering_actuator_failure_is_nonfatal_and_disables_servotronic_output() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    activate_devices(kernel)

    commit = kernel.dispatch(SteeringActuatorFailed(2.0, "actuator"))

    assert commit is not None
    assert commit.changed_topics == {StateTopic.HEALTH}
    assert kernel.health.steering_actuator_fault is not None
    assert kernel.health.steering_actuator_fault.kind is RuntimeFaultKind.STEERING_ACTUATOR
    assert kernel.health.steering_actuator_fault.message == "actuator"
    assert kernel.health.fatal is False
    with pytest.raises(FeatureUnavailable, match="servotronic output adapter is faulted"):
        kernel.dispatch(ExecuteOperatorIntent(SetMaximumAssistance(True)))


def test_speed_staleness_uses_explicit_input_times() -> None:
    kernel = CoordinatorKernel(router=SpeedRouter())
    speed_frame = CanFrame(0x123, b"\x2a")
    kernel.dispatch(KernelStarted(0.0))

    kernel.dispatch(ReceivedCanFrame(CanNetwork.FCAN, speed_frame, 0.0))
    assert kernel.snapshot().speed_valid is True

    kernel.dispatch(TimerElapsed(0.5))
    assert kernel.snapshot().speed_valid is True

    kernel.dispatch(TimerElapsed(1.5))
    assert kernel.snapshot().speed_valid is False

    kernel.dispatch(ReceivedCanFrame(CanNetwork.FCAN, speed_frame, 2.0))
    assert kernel.snapshot().speed_valid is True


def test_old_queued_speed_frame_keeps_ingress_time_when_processed_later() -> None:
    kernel = CoordinatorKernel(router=SpeedRouter())
    kernel.dispatch(KernelStarted(0.0))

    kernel.dispatch(ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x2a"), received_at=1.0))
    kernel.dispatch(TimerElapsed(5.0))

    assert kernel.state.speed_sample == SpeedSample(42.0, 1.0, CanNetwork.FCAN)
    assert kernel.snapshot().speed_valid is False


def test_old_simulated_speed_frame_cannot_clear_failsafe_when_processed_late() -> None:
    kernel = CoordinatorKernel(router=SimulationProtocolRouter())
    kernel.dispatch(KernelStarted(0.0))
    kernel.dispatch(TimerElapsed(5.0))

    commit = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.FCAN,
            encode_simulated_speed(42.0),
            received_at=1.0,
        )
    )

    assert commit is not None
    assert commit.snapshot.speed_valid is False
    assert commit.changed_topics == {StateTopic.VEHICLE}
    assert commit.effects == ()


def test_startup_and_shutdown_are_idempotent() -> None:
    kernel = CoordinatorKernel()

    assert kernel.dispatch(KernelStarted(1.0)) is not None
    assert kernel.dispatch(KernelStarted(2.0)) is None
    shutdown = kernel.dispatch(ShutdownRequested(3.0))
    assert shutdown is not None
    assert shutdown.effects == ()
    assert kernel.dispatch(ShutdownRequested(4.0)) is None
    assert kernel.dispatch(TimerElapsed(5.0)) is None
    assert kernel.diagnostics().lifecycle is KernelLifecycle.STOPPED
    assert kernel.diagnostics().revision == 2


@pytest.mark.parametrize(
    ("failure", "fatal"),
    [
        (CanEffectExecutionFailed(CanNetwork.KCAN, 4.0, "CAN shutdown failed"), True),
        (SteeringActuatorFailed(4.0, "actuator shutdown failed"), False),
    ],
)
def test_typed_effect_failure_updates_health_after_stop(
    failure: CanEffectExecutionFailed | SteeringActuatorFailed,
    fatal: bool,
) -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(1.0))
    kernel.dispatch(ShutdownRequested(2.0))
    revision = kernel.diagnostics().revision

    commit = kernel.dispatch(failure)

    assert commit is not None
    assert commit.changed_topics == {StateTopic.HEALTH}
    assert kernel.diagnostics().revision == revision + 1
    assert kernel.health.fatal is fatal
    assert kernel.diagnostics().lifecycle is KernelLifecycle.STOPPED
