from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.domain.devices.catalogue import DeviceLifecycleStatus, DeviceRole
from e87canbus.kernel import (
    CoordinatorKernel,
    KernelStarted,
    ReceivedCanFrame,
    StateTopic,
    TimerElapsed,
)
from e87canbus.protocol.can import (
    DeviceHeartbeatPayload,
    DeviceHelloPayload,
    encode_heartbeat,
    encode_hello,
)

IDS = CustomCanIds()


def test_only_servotronic_has_a_registry_entry() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    assert len(kernel.registry) == 1
    assert kernel.registry[0].role is DeviceRole.SERVOTRONIC_CONTROLLER
    assert kernel.registry[0].status is DeviceLifecycleStatus.NOT_FOUND


def test_servotronic_hello_and_heartbeat_activate_registry() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    pending = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, 1, 0), IDS.servotronic_controller_hello),
            1.0,
        )
    )
    active = kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                IDS.servotronic_controller_heartbeat,
            ),
            1.1,
        )
    )

    assert pending is not None and active is not None
    assert kernel.registry[0].status is DeviceLifecycleStatus.ACTIVE
    assert StateTopic.DEVICES in active.changed_topics
    assert any(
        request.effect.__class__.__name__ == "SendRegistryFrame" for request in pending.effects
    )


def test_servotronic_entry_expires_after_contact_timeout() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_hello(DeviceHelloPayload(1, 1, 1, 0), IDS.servotronic_controller_hello),
            1.0,
        )
    )
    kernel.dispatch(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            encode_heartbeat(
                DeviceHeartbeatPayload(1, 1, kernel.controller_session_id, 0, 0),
                IDS.servotronic_controller_heartbeat,
            ),
            1.1,
        )
    )

    commit = kernel.dispatch(TimerElapsed(5.0))

    assert commit is not None
    assert kernel.registry[0].status is DeviceLifecycleStatus.STALE
    assert StateTopic.DEVICES in commit.changed_topics
