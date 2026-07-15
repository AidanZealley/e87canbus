import logging

import pytest
from e87canbus.application.events import (
    ApplicationEvent,
    ButtonLedState,
    ButtonPressed,
    LedColour,
    SetButtonLeds,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
)
from e87canbus.application.state import SpeedSample, SteeringMode
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    INITIAL_KERNEL_TOPICS,
    CanEffectExecutionFailed,
    CanReaderFailed,
    CoordinatorKernel,
    InboxOverflowed,
    KernelLifecycle,
    KernelStarted,
    ReceivedCanFrame,
    RuntimeFault,
    RuntimeFaultKind,
    RuntimeHealth,
    SetMaximumAssistance,
    SetSteeringMode,
    ShutdownRequested,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter, encode_simulated_speed

AUTO_LEDS = ButtonLedState((LedColour.BLUE,) + (LedColour.OFF,) * 15)
MANUAL_LEDS = ButtonLedState((LedColour.AMBER,) + (LedColour.OFF,) * 15)
MAXIMUM_LEDS = ButtonLedState(
    (LedColour.AMBER, LedColour.OFF, LedColour.OFF, LedColour.WHITE) + (LedColour.OFF,) * 12
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
    assert [commit.revision for commit in first_commits if commit is not None] == [1, 2, 3]
    assert first_commits[0] is not None
    assert first_commits[0].changed_topics == INITIAL_KERNEL_TOPICS
    assert first_commits[0].effects == (
        SetButtonLeds(AUTO_LEDS),
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
    )
    assert first_commits[1] is not None
    assert first_commits[1].changed_topics == {
        StateTopic.STEERING,
        StateTopic.BUTTONS,
    }
    assert first_commits[1].snapshot.steering_mode is SteeringMode.MANUAL
    assert first_commits[1].effects == (SetButtonLeds(MANUAL_LEDS),)
    assert first_commits[2] is not None
    assert first_commits[2].effects == (SetSteeringAssistance(0.0, SteeringCommandReason.MANUAL),)
    assert first_commits[2].changed_topics == frozenset()
    assert first_commits[2].state_changed is False


def test_semantic_set_inputs_are_repeat_safe_with_exact_topics_and_effects() -> None:
    kernel = CoordinatorKernel()
    assert kernel.dispatch(KernelStarted(0.0)) is not None

    maximum = kernel.dispatch(SetMaximumAssistance(True))
    repeated_maximum = kernel.dispatch(SetMaximumAssistance(True))
    hidden_mode = kernel.dispatch(SetSteeringMode(SteeringMode.MANUAL, 4))
    repeated_hidden_mode = kernel.dispatch(SetSteeringMode(SteeringMode.MANUAL, 4))
    normal = kernel.dispatch(SetMaximumAssistance(False))
    repeated_normal = kernel.dispatch(SetMaximumAssistance(False))
    auto = kernel.dispatch(SetSteeringMode(SteeringMode.AUTO))
    repeated_auto = kernel.dispatch(SetSteeringMode(SteeringMode.AUTO))

    assert maximum is not None
    assert maximum.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert maximum.effects == (SetButtonLeds(MAXIMUM_LEDS),)
    assert maximum.snapshot.maximum_assistance_active is True

    for repeated in (
        repeated_maximum,
        hidden_mode,
        repeated_hidden_mode,
        repeated_normal,
        repeated_auto,
    ):
        assert repeated is not None
        assert repeated.changed_topics == frozenset()
        assert repeated.effects == ()
        assert repeated.state_changed is False

    assert normal is not None
    assert normal.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert normal.effects == (SetButtonLeds(MANUAL_LEDS),)
    assert normal.snapshot.steering_mode is SteeringMode.MANUAL
    assert normal.snapshot.manual_assistance_level == 4
    assert normal.snapshot.maximum_assistance_active is False

    assert auto is not None
    assert auto.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert auto.effects == (SetButtonLeds(AUTO_LEDS),)
    assert auto.snapshot.steering_mode is SteeringMode.AUTO
    assert auto.snapshot.manual_assistance_level == 4


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


def test_button_topic_is_backed_by_one_complete_immutable_led_projection() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    commit = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            0.1,
        )
    )

    assert commit is not None
    led_effects = tuple(effect for effect in commit.effects if isinstance(effect, SetButtonLeds))
    assert commit.changed_topics == {StateTopic.STEERING, StateTopic.BUTTONS}
    assert led_effects == (SetButtonLeds(MANUAL_LEDS),)
    assert len(led_effects[0].colours.colours) == 16


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

    commit = kernel.dispatch(kernel_input)

    assert kernel_input.network is not None
    fault = kernel.health.for_network(kernel_input.network).fault
    assert fault is not None
    assert fault.kind is kind
    assert kernel.health.fatal is True
    if fallback_reason is None:
        assert commit is None
    else:
        assert commit is not None
        assert commit.changed_topics == {StateTopic.HEALTH}
        assert commit.effects == (SetSteeringAssistance(0.0, fallback_reason),)


def test_steering_actuator_failure_has_explicit_fatal_health() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    commit = kernel.dispatch(SteeringActuatorFailed(2.0, "actuator"))

    assert commit is None
    assert kernel.health.steering_actuator_fault is not None
    assert kernel.health.steering_actuator_fault.kind is RuntimeFaultKind.STEERING_ACTUATOR
    assert kernel.health.steering_actuator_fault.message == "actuator"
    assert kernel.health.fatal is True


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
    assert shutdown.effects == (SetSteeringAssistance(0.0, SteeringCommandReason.SHUTDOWN),)
    assert kernel.dispatch(ShutdownRequested(4.0)) is None
    assert kernel.dispatch(TimerElapsed(5.0)) is None
    assert kernel.diagnostics().lifecycle is KernelLifecycle.STOPPED
    assert kernel.diagnostics().revision == 2


@pytest.mark.parametrize(
    "failure",
    [
        CanEffectExecutionFailed(CanNetwork.KCAN, 4.0, "CAN shutdown failed"),
        SteeringActuatorFailed(4.0, "actuator shutdown failed"),
    ],
)
def test_typed_effect_failure_updates_health_after_stop_without_commit(
    failure: CanEffectExecutionFailed | SteeringActuatorFailed,
) -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(1.0))
    kernel.dispatch(ShutdownRequested(2.0))
    revision = kernel.diagnostics().revision

    commit = kernel.dispatch(failure)

    assert commit is None
    assert kernel.health.fatal is True
    assert kernel.diagnostics().lifecycle is KernelLifecycle.STOPPED
    assert kernel.diagnostics().revision == revision
