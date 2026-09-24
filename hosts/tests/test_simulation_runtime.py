from e87canbus.kernel import StateTopic
from e87canbus.runners.simulation.commands import ResetSimulation, SetVehicleSignal
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime
from e87canbus.runners.simulation.signals import VehicleSignal


def test_simulation_uses_vehicle_input_buses() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start(lambda _: True)

    assert len(runtime.pi_buses) == 3
    assert not hasattr(runtime, "servotronic")


def test_simulated_vehicle_speed_crosses_can_decoder() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start(lambda _: True)

    execution = runtime.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))

    assert runtime.projection()[0].vehicle_speed_kph == 42.5
    assert StateTopic.VEHICLE in execution.changed_topics


def test_reset_restores_desired_state_and_new_session() -> None:
    runtime = SimulatedControllerRuntime()
    runtime.start(lambda _: True)
    runtime.execute(SetVehicleSignal(VehicleSignal.SPEED, 42.5))

    runtime.execute(ResetSimulation())

    assert runtime.projection()[0].vehicle_speed_kph == 0.0
    assert runtime.projection()[2] == 2
