"""Declarative synthetic vehicle signal storage shared by bench and simulator."""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.config import CanNetwork
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.runners.simulation.commands import SetVehicleSignal, SilenceVehicleSignal
from e87canbus.runners.simulation.protocol import VEHICLE_SIGNALS
from e87canbus.runners.simulation.signals import VehicleSignal

VehicleCommand = SetVehicleSignal | SilenceVehicleSignal


@dataclass
class SyntheticVehicleSource:
    """Retain encoded frames so every selected signal shares refresh behavior."""

    speed_network: CanNetwork = CanNetwork.FCAN
    active: dict[VehicleSignal, RoutedCanFrame] = field(default_factory=dict)

    def execute(self, command: VehicleCommand) -> tuple[RoutedCanFrame, ...]:
        if isinstance(command, SilenceVehicleSignal):
            self.active.pop(command.signal, None)
            return ()

        spec = VEHICLE_SIGNALS[command.signal]
        network = self.speed_network if command.signal is VehicleSignal.SPEED else spec.network
        routed = RoutedCanFrame(network, spec.encode(command.value))
        self.active[command.signal] = routed
        return (routed,)

    def emit(self) -> tuple[RoutedCanFrame, ...]:
        return tuple(self.active.values())
