from e87canbus.config import CanNetwork
from e87canbus.domain.events import ButtonPressed
from e87canbus.domain.state import SteeringMode
from e87canbus.kernel import CoordinatorKernel, KernelStarted, ReceivedCanFrame, StateTopic
from e87canbus.protocol.can import CanFrame
from e87canbus.runners.simulation.protocol import SimulationProtocolRouter, encode_simulated_speed


def test_retired_button_can_id_is_ignored() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    result = kernel.dispatch(ReceivedCanFrame(CanNetwork.KCAN, CanFrame(0x700, b"\x00\x01"), 1.0))

    assert result is None
    assert kernel.snapshot().steering_mode is SteeringMode.AUTO
    assert kernel.health.networks[0].ignored_frames == 1


def test_vehicle_can_still_updates_complete_projection() -> None:
    kernel = CoordinatorKernel(router=SimulationProtocolRouter())
    kernel.dispatch(KernelStarted(0.0))

    commit = kernel.dispatch(ReceivedCanFrame(CanNetwork.FCAN, encode_simulated_speed(42.5), 1.0))

    assert commit is not None
    assert commit.snapshot.vehicle_speed_kph == 42.5
    assert commit.snapshot.speed_valid
    assert StateTopic.VEHICLE in commit.changed_topics


def test_unassigned_direct_button_press_has_no_transient_feedback() -> None:
    kernel = CoordinatorKernel()
    kernel.dispatch(KernelStarted(0.0))

    assert kernel.dispatch(ButtonPressed(0, 1.0)) is None
    assert kernel.snapshot().steering_mode is SteeringMode.AUTO
    assert not hasattr(kernel.state, "button_feedback")
