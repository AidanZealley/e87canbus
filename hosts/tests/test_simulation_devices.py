from e87canbus.config import CanNetwork
from e87canbus.domain.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.runners.simulation.bus import InMemoryCanTopology
from e87canbus.runners.simulation.commands import (
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.devices import SimulatedServotronicPeer, SimulatedVehicleNode
from e87canbus.runners.simulation.protocol import (
    encode_simulated_coolant_temperature,
    encode_simulated_engine_rpm,
    encode_simulated_oil_temperature,
    encode_simulated_speed,
)
from e87canbus.runners.simulation.signals import VehicleSignal
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_simulated_vehicle_stores_and_emits_speed_as_an_external_fcan_frame() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.FCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    vehicle.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))
    frame = encode_simulated_speed(42.5)

    assert pi_bus.receive(timeout_s=0) == frame

    vehicle.emit()
    assert pi_bus.receive(timeout_s=0) == frame

    vehicle.execute(SilenceVehicleSignal(VehicleSignal.SPEED))
    vehicle.emit()
    assert pi_bus.receive(timeout_s=0) is None


def test_simulated_vehicle_engine_signals_emit_and_silence_independently_on_ptcan() -> None:
    topology = InMemoryCanTopology()
    pi_bus = topology.create_bus(CanNetwork.PTCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork}
    )

    vehicle.execute(SetVehicleSignal(VehicleSignal.RPM, 3500))
    vehicle.execute(SetVehicleSignal(VehicleSignal.OIL_TEMPERATURE, 112.54))
    vehicle.execute(SetVehicleSignal(VehicleSignal.COOLANT_TEMPERATURE, 98.0))
    assert [pi_bus.receive(timeout_s=0) for _ in range(3)] == [
        encode_simulated_engine_rpm(3500),
        encode_simulated_oil_temperature(112.5),
        encode_simulated_coolant_temperature(98.0),
    ]

    vehicle.execute(SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE))
    vehicle.execute(SilenceVehicleSignal(VehicleSignal.OIL_TEMPERATURE))

    vehicle.emit()
    assert [pi_bus.receive(timeout_s=0) for _ in range(2)] == [
        encode_simulated_engine_rpm(3500),
        encode_simulated_coolant_temperature(98.0),
    ]


def test_simulated_vehicle_sweep_is_generated_from_continuous_virtual_car_time() -> None:
    clock = MutableClock(10.0)
    topology = InMemoryCanTopology(clock=clock)
    fcan = topology.create_bus(CanNetwork.FCAN, "pi")
    ptcan = topology.create_bus(CanNetwork.PTCAN, "pi")
    vehicle = SimulatedVehicleNode(
        {network: topology.create_bus(network, "simulated-vehicle") for network in CanNetwork},
        SyntheticVehicleSource(clock=clock),
    )

    vehicle.execute(SetVehicleSweep(True))
    assert fcan.receive(timeout_s=0) == encode_simulated_speed(0.0)
    assert [ptcan.receive(timeout_s=0) for _ in range(3)] == [
        encode_simulated_engine_rpm(0),
        encode_simulated_oil_temperature(-40.0),
        encode_simulated_coolant_temperature(-40.0),
    ]

    clock.now = 13.0
    vehicle.emit()
    assert fcan.receive(timeout_s=0) == encode_simulated_speed(150.0)
    assert [ptcan.receive(timeout_s=0) for _ in range(3)] == [
        encode_simulated_engine_rpm(4500),
        encode_simulated_oil_temperature(55.0),
        encode_simulated_coolant_temperature(40.0),
    ]

    vehicle.execute(SetVehicleSweep(False))
    clock.now = 16.0
    vehicle.emit()
    assert fcan.receive(timeout_s=0) == encode_simulated_speed(150.0)


def test_simulated_steering_watchdog_removes_assistance_after_silence() -> None:
    clock = MutableClock()
    controller = SimulatedServotronicPeer(0.25, clock)
    command = SetSteeringAssistance(0.75, SteeringCommandReason.AUTO)

    controller.set_assistance(command)
    clock.now = 0.251

    assert controller.effective_assistance == 0.0
    assert controller.last_command_reason is SteeringCommandReason.AUTO
    assert controller.watchdog_timed_out is True
