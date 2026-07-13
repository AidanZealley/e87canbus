import logging

import pytest
from e87canbus.application.events import (
    ApplicationEvent,
    ButtonPressed,
    LedColour,
    SetButtonLed,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
)
from e87canbus.application.state import SpeedSample, SteeringMode
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    CanEffectExecutionFailed,
    CanReaderFailed,
    CoordinatorKernel,
    InboxOverflowed,
    KernelLifecycle,
    KernelStarted,
    ReceivedCanFrame,
    RuntimeFaultKind,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter, encode_simulated_speed


class SpeedRouter(ProtocolRouter):
    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | None:
        return SpeedObserved(
            SpeedSample(float(routed.frame.data[0]), observed_at, routed.network)
        )


def test_protocol_router_discards_releases_and_scopes_button_decode_to_kcan() -> None:
    ids = CustomCanIds()
    router = ProtocolRouter(ids)
    pressed = CanFrame(ids.button_event, b"\x00\x01")
    released = CanFrame(ids.button_event, b"\x00\x00")

    assert router.decode(RoutedCanFrame(CanNetwork.PTCAN, pressed), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.FCAN, pressed), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, released), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, pressed), 1.0) == ButtonPressed(0)


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
    assert first_commits[0].effects == (
        SetButtonLed(0, LedColour.BLUE),
        SetButtonLed(3, LedColour.OFF),
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
    )
    assert first_commits[1] is not None
    assert first_commits[1].snapshot.steering_mode is SteeringMode.MANUAL
    assert first_commits[1].effects == (SetButtonLed(0, LedColour.AMBER),)
    assert first_commits[2] is not None
    assert first_commits[2].effects == (
        SetSteeringAssistance(0.0, SteeringCommandReason.MANUAL),
    )
    assert first_commits[2].state_changed is False


def test_unknown_and_malformed_frames_create_no_commits(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    with caplog.at_level(logging.WARNING):
        unknown = kernel.dispatch(
            ReceivedCanFrame(CanNetwork.KCAN, CanFrame(0x123, b"\x00"), 1.0)
        )
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
    assert "ignored malformed recognized frame" in caplog.text


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
        assert commit.effects == (
            SetSteeringAssistance(0.0, fallback_reason),
        )


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

    kernel.dispatch(
        ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x2a"), received_at=1.0)
    )
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
    assert commit.effects == ()


def test_startup_and_shutdown_are_idempotent() -> None:
    kernel = CoordinatorKernel()

    assert kernel.dispatch(KernelStarted(1.0)) is not None
    assert kernel.dispatch(KernelStarted(2.0)) is None
    shutdown = kernel.dispatch(ShutdownRequested(3.0))
    assert shutdown is not None
    assert shutdown.effects == (
        SetSteeringAssistance(0.0, SteeringCommandReason.SHUTDOWN),
    )
    assert kernel.dispatch(ShutdownRequested(4.0)) is None
    assert kernel.dispatch(TimerElapsed(5.0)) is None
    assert kernel.diagnostics().lifecycle is KernelLifecycle.STOPPED
    assert kernel.diagnostics().revision == 2
