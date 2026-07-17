import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from e87canbus.application.events import (
    RGB_BLUE,
    RGB_OFF,
    RGB_RED,
    ButtonFeedbackDeadlineReached,
    SetButtonLeds,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.application.state import SteeringMode
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.device import DeviceLifecycleStatus, DeviceRole
from e87canbus.device_registry import FeatureUnavailable
from e87canbus.output import EffectRequest, SendRegistryFrame
from e87canbus.protocol.can import (
    CanFrame,
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)
from e87canbus.runtime import (
    CoordinatorKernel,
    DeviceAdapterFailed,
    KernelStarted,
    ReceivedCanFrame,
    SetMaximumAssistance,
    SetSteeringMode,
    StateTopic,
    TimerElapsed,
)

IDS = CustomCanIds()


def hello(
    role: DeviceRole,
    *,
    version: int = 1,
    device_id: int = 1,
    session: int = 0x1234,
    sequence: int = 0,
) -> CanFrame:
    arbitration_id = (
        IDS.button_pad_hello if role is DeviceRole.BUTTON_PAD else IDS.servotronic_controller_hello
    )
    return encode_hello(DeviceHelloPayload(version, device_id, session, sequence), arbitration_id)


def heartbeat(
    kernel: CoordinatorKernel,
    role: DeviceRole,
    *,
    session: int = 0x1234,
    controller_session: int | None = None,
    sequence: int = 0,
    status: int = 0,
) -> CanFrame:
    arbitration_id = (
        IDS.button_pad_heartbeat
        if role is DeviceRole.BUTTON_PAD
        else IDS.servotronic_controller_heartbeat
    )
    return encode_heartbeat(
        DeviceHeartbeatPayload(
            1,
            session,
            kernel.controller_session_id if controller_session is None else controller_session,
            sequence,
            status,
        ),
        arbitration_id,
    )


def receive(
    kernel: CoordinatorKernel,
    frame: CanFrame,
    at: float,
) -> object:
    commit = kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, frame, at))
    assert commit is not None
    return commit


def register(
    kernel: CoordinatorKernel,
    role: DeviceRole,
    *,
    session: int = 0x1234,
    at: float = 1.0,
) -> None:
    receive(kernel, hello(role, session=session), at)
    receive(kernel, heartbeat(kernel, role, session=session), at + 0.1)


def test_kernel_boot_creates_nonzero_session_and_two_not_found_entries() -> None:
    kernel = CoordinatorKernel()
    next_kernel = CoordinatorKernel()

    startup = kernel.dispatch(KernelStarted(10.0))

    assert kernel.controller_session_id != 0
    assert next_kernel.controller_session_id != kernel.controller_session_id
    assert startup is not None
    assert startup.changed_topics == {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.LIGHTING,
        StateTopic.HEALTH,
        StateTopic.DEVICES,
    }
    assert [entry.status for entry in kernel.registry] == [
        DeviceLifecycleStatus.NOT_FOUND,
        DeviceLifecycleStatus.NOT_FOUND,
    ]


def test_controller_session_changes_across_process_restarts() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    environment = {
        **os.environ,
        "PYTHONPATH": str(repository_root / "coordinator" / "src"),
    }
    command = [
        sys.executable,
        "-c",
        "from e87canbus.runtime import CoordinatorKernel; "
        "print(CoordinatorKernel().controller_session_id)",
    ]

    sessions = {
        int(
            subprocess.run(
                command,
                cwd=repository_root,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        )
        for _ in range(4)
    }

    assert len(sessions) > 1
    assert 0 not in sessions


def test_hello_pending_then_healthy_heartbeat_active_and_syncs_leds() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    pending = receive(kernel, hello(DeviceRole.BUTTON_PAD), 1.0)
    active = receive(kernel, heartbeat(kernel, DeviceRole.BUTTON_PAD), 1.1)

    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.ACTIVE
    assert pending.changed_topics == {StateTopic.DEVICES}
    assert isinstance(pending.effects[0], EffectRequest)
    assert isinstance(pending.effects[0].effect, SendRegistryFrame)
    assert active.changed_topics == {StateTopic.DEVICES}
    assert active.effects[0].effect.routed.frame.arbitration_id == IDS.button_pad_welcome_ack
    assert active.effects[1].effect == SetButtonLeds(
        replace(
                active.effects[1].effect.rgb,
            rgb=(RGB_BLUE,) + (RGB_OFF,) * 15,
        )
    )


def test_duplicate_heartbeat_renews_without_devices_topic_publication() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    register(kernel, DeviceRole.BUTTON_PAD)

    duplicate = receive(kernel, heartbeat(kernel, DeviceRole.BUTTON_PAD, sequence=0), 2.0)

    assert duplicate.changed_topics == frozenset()
    assert duplicate.effects[0].effect.routed.frame.arbitration_id == IDS.button_pad_welcome_ack
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.ACTIVE


def test_wrong_session_old_sequence_and_controller_session_are_ignored() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    register(kernel, DeviceRole.BUTTON_PAD)

    for frame in (
        heartbeat(kernel, DeviceRole.BUTTON_PAD, session=0x9999, sequence=1),
        heartbeat(kernel, DeviceRole.BUTTON_PAD, controller_session=0xFFFF, sequence=1),
        heartbeat(kernel, DeviceRole.BUTTON_PAD, sequence=200),
    ):
        assert kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, frame, 2.0)) is None

    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.ACTIVE


def test_timeout_marks_stale_and_a_new_session_reenters_pending() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    register(kernel, DeviceRole.BUTTON_PAD)

    stale = kernel.dispatch(TimerElapsed(4.2))
    assert stale is not None
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.STALE
    assert StateTopic.DEVICES in stale.changed_topics

    receive(kernel, hello(DeviceRole.BUTTON_PAD, session=0x2222), 5.0)
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.PENDING


def test_stale_same_session_recovery_uses_independent_hello_sequence() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    register(kernel, DeviceRole.BUTTON_PAD)
    for sequence in range(1, 201):
        receive(
            kernel,
            heartbeat(kernel, DeviceRole.BUTTON_PAD, sequence=sequence),
            2.0,
        )

    kernel.dispatch(TimerElapsed(5.1))
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.STALE

    recovered = receive(
        kernel,
        hello(DeviceRole.BUTTON_PAD, sequence=1),
        5.2,
    )

    assert recovered.changed_topics == {StateTopic.DEVICES}
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.PENDING


def test_hello_sequence_wrap_from_255_to_zero_is_accepted() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    receive(kernel, hello(DeviceRole.BUTTON_PAD, sequence=255), 1.0)
    wrapped = receive(kernel, hello(DeviceRole.BUTTON_PAD, sequence=0), 2.0)

    assert wrapped.changed_topics == frozenset()
    assert wrapped.effects[0].effect.routed.frame.arbitration_id == IDS.button_pad_welcome_ack


def test_incompatible_observation_expires_to_stale() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    incompatible = receive(kernel, hello(DeviceRole.BUTTON_PAD, version=2), 1.0)
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.INCOMPATIBLE
    assert incompatible.effects[0].effect.routed.frame.data[0] & 0x0F == 1

    kernel.dispatch(TimerElapsed(16.0))
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.STALE


def test_older_incompatible_hello_does_not_renew_observation_deadline() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    receive(kernel, hello(DeviceRole.BUTTON_PAD, version=2, sequence=10), 1.0)
    ignored = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            hello(DeviceRole.BUTTON_PAD, version=2, sequence=9),
            10.0,
        )
    )

    assert ignored is None
    expired = kernel.dispatch(TimerElapsed(16.0))
    assert expired is not None
    assert expired.changed_topics == {StateTopic.DEVICES}
    assert kernel.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.STALE


def test_button_input_is_ignored_until_active_and_feedback_is_independently_timed() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    button = CanFrame(IDS.button_event, b"\x00\x01")

    assert kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, button, 1.0)) is None
    register(kernel, DeviceRole.BUTTON_PAD, at=2.0)

    unavailable = kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, button, 3.0))
    assert unavailable is not None
    assert kernel.state.button_feedback_deadlines[0] == pytest.approx(3.5)
    assert unavailable.effects == (
        EffectRequest(
            SetButtonLeds(
                replace(
                    unavailable.effects[0].effect.rgb,
            rgb=(RGB_RED,) + (RGB_OFF,) * 15,
                )
            )
        ),
    )

    expired = kernel.dispatch(ButtonFeedbackDeadlineReached(3.5))
    assert expired is not None
    assert kernel.state.button_feedback_deadlines[0] is None
    assert expired.effects[0].effect.rgb.rgb[0] == RGB_BLUE


def test_steering_operations_are_gated_until_active_and_adapter_fault_is_nonfatal() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    with pytest.raises(FeatureUnavailable, match="servotronic controller is not_found"):
        kernel.dispatch(SetMaximumAssistance(True))

    button_failure = kernel.dispatch(
        DeviceAdapterFailed(DeviceRole.BUTTON_PAD, 1.0, "adapter")
    )
    assert button_failure is not None
    assert button_failure.changed_topics == {StateTopic.HEALTH}
    with pytest.raises(FeatureUnavailable):
        kernel.dispatch(SetSteeringMode(SteeringMode.MANUAL, 2))

    register(kernel, DeviceRole.SERVOTRONIC_CONTROLLER)
    kernel.dispatch(SetMaximumAssistance(True))
    failed = kernel.dispatch(DeviceAdapterFailed(DeviceRole.SERVOTRONIC_CONTROLLER, 2.0, "adapter"))

    assert failed is not None
    assert kernel.snapshot().maximum_assistance_active is False
    assert kernel.health.fatal is False
    assert kernel.health_for_device(DeviceRole.SERVOTRONIC_CONTROLLER).fault is not None


def test_servotronic_fault_clears_maximum_and_healthy_recovery_syncs_normal_output() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    register(kernel, DeviceRole.SERVOTRONIC_CONTROLLER)
    kernel.dispatch(SetMaximumAssistance(True))

    fault = receive(
        kernel,
        heartbeat(kernel, DeviceRole.SERVOTRONIC_CONTROLLER, sequence=1, status=7),
        2.0,
    )
    assert (
        kernel.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).status is DeviceLifecycleStatus.FAULT
    )
    assert kernel.snapshot().maximum_assistance_active is False
    assert all(not isinstance(request.effect, SetSteeringAssistance) for request in fault.effects)

    recovery = receive(
        kernel,
        heartbeat(kernel, DeviceRole.SERVOTRONIC_CONTROLLER, sequence=2, status=0),
        3.0,
    )
    assert (
        kernel.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).status
        is DeviceLifecycleStatus.ACTIVE
    )
    assert any(
        request.effect == SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED)
        for request in recovery.effects
    )
