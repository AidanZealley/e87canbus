"""The external simulated vehicle node with explicitly synthetic messages."""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.runners.simulation.commands import (
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource


@dataclass
class SimulatedVehicleNode:
    """External simulation node with explicitly synthetic vehicle messages."""

    buses: dict[CanNetwork, CanEndpoint]
    signals: SyntheticVehicleSource = field(default_factory=SyntheticVehicleSource)

    def execute(self, command: SetVehicleSignal | SilenceVehicleSignal | SetVehicleSweep) -> None:
        self._send(self.signals.execute(command))

    def emit(self) -> None:
        self._send(self.signals.emit())

    def _send(self, frames: tuple[RoutedCanFrame, ...]) -> None:
        for routed in frames:
            self.buses[routed.network].send(routed.frame)
