"""Simulated project CAN devices.

One module per virtual device, all sharing the ``SimulatedRegistryPeer`` base.
Import from this package (``from e87canbus.runners.simulation.devices import ...``).
"""

from e87canbus.runners.simulation.devices.high_beam import SimulatedHighBeamActuator
from e87canbus.runners.simulation.devices.neotrellis import SimulatedNeoTrellisNode
from e87canbus.runners.simulation.devices.peer import SimulatedDeviceState, SimulatedRegistryPeer
from e87canbus.runners.simulation.devices.servotronic import SimulatedServotronicPeer
from e87canbus.runners.simulation.devices.vehicle import SimulatedVehicleNode

__all__ = [
    "SimulatedDeviceState",
    "SimulatedHighBeamActuator",
    "SimulatedNeoTrellisNode",
    "SimulatedRegistryPeer",
    "SimulatedServotronicPeer",
    "SimulatedVehicleNode",
]
