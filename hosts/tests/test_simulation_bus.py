from e87canbus.protocol.can import CanFrame
from e87canbus.runners.simulation.bus import InMemoryCanNetwork


def test_network_delivers_vehicle_frame_to_other_endpoint() -> None:
    network = InMemoryCanNetwork()
    vehicle = network.create_bus("vehicle")
    coordinator = network.create_bus("coordinator")
    frame = CanFrame(0x700, b"\x02\x01")

    vehicle.send(frame)

    assert coordinator.receive(timeout_s=0) == frame
    assert vehicle.receive(timeout_s=0) is None
