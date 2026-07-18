"""Declarative synthetic vehicle signal storage shared by bench and simulator."""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.simulation.commands import SetVehicleSignal, SilenceVehicleSignal
from e87canbus.simulation.protocol import VEHICLE_SIGNALS
from e87canbus.simulation.signals import VehicleSignal

VehicleCommand = SetVehicleSignal | SilenceVehicleSignal


@dataclass
class SyntheticVehicleSource:
    """Retain encoded frames so every selected signal shares refresh behavior."""

    active: dict[VehicleSignal, RoutedCanFrame] = field(default_factory=dict)

    def execute(self, command: VehicleCommand) -> tuple[RoutedCanFrame, ...]:
        if isinstance(command, SilenceVehicleSignal):
            self.active.pop(command.signal, None)
            return ()

        spec = VEHICLE_SIGNALS[command.signal]
        routed = RoutedCanFrame(spec.network, spec.encode(command.value))
        self.active[command.signal] = routed
        return (routed,)

    def emit(self) -> tuple[RoutedCanFrame, ...]:
        return tuple(self.active.values())
