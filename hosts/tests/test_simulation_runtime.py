from e87canbus.config import CanNetwork
from e87canbus.runners.simulation.commands import ResetSimulation, SetVehicleSignal
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime
from e87canbus.runners.simulation.signals import VehicleSignal


def test_simulation_has_vehicle_and_servotronic_peers_without_button_peer() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start()

    assert runtime.topology.nodes(CanNetwork.KCAN) == (
        "pi",
        "simulated-vehicle",
        "servotronic-emulator",
    )
    assert not hasattr(runtime, "neotrellis")


def test_simulated_vehicle_speed_crosses_can_decoder() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start()

    execution = runtime.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))

    assert runtime.projection()[0].vehicle_speed_kph == 42.5
    assert any(
        event["network"] == "fcan" and event["source"] == "simulated-vehicle"
        for event in execution.events
    )


def test_reset_restores_desired_state_and_new_session() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start()
    runtime.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))

    runtime.execute(ResetSimulation())

    assert runtime.projection()[0].vehicle_speed_kph == 0.0
    assert runtime.projection()[2].simulation_session_id == 2
