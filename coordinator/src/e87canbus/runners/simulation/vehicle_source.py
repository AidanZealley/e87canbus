"""Declarative synthetic vehicle signal storage shared by bench and simulator."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from e87canbus.config import CanNetwork
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.runners.simulation.commands import (
    SetVehicleSignal,
    SetVehicleSweep,
    SilenceVehicleSignal,
)
from e87canbus.runners.simulation.protocol import VEHICLE_SIGNALS
from e87canbus.runners.simulation.signals import VehicleSignal

VehicleCommand = SetVehicleSignal | SilenceVehicleSignal | SetVehicleSweep

VEHICLE_SWEEP_PERIOD_S = 12.0
VEHICLE_SWEEP_RANGES: dict[VehicleSignal, tuple[float, float]] = {
    VehicleSignal.SPEED: (0.0, 300.0),
    VehicleSignal.RPM: (0.0, 9_000.0),
    VehicleSignal.OIL_TEMPERATURE: (-40.0, 150.0),
    VehicleSignal.COOLANT_TEMPERATURE: (-40.0, 120.0),
}


@dataclass
class SyntheticVehicleSource:
    """Retain encoded frames so every selected signal shares refresh behavior."""

    speed_network: CanNetwork = CanNetwork.FCAN
    clock: Callable[[], float] = time.monotonic
    active: dict[VehicleSignal, RoutedCanFrame] = field(default_factory=dict)
    sweep_started_at: float | None = None

    def execute(self, command: VehicleCommand) -> tuple[RoutedCanFrame, ...]:
        if isinstance(command, SetVehicleSweep):
            if not command.enabled:
                self.sweep_started_at = None
                return ()
            self.sweep_started_at = self.clock()
            return self.emit()

        # An explicit signal edit takes ownership back from the automatic source.
        self.sweep_started_at = None
        if isinstance(command, SilenceVehicleSignal):
            self.active.pop(command.signal, None)
            return ()

        return (self._set(command.signal, command.value),)

    def emit(self) -> tuple[RoutedCanFrame, ...]:
        if self.sweep_started_at is not None:
            elapsed = self.clock() - self.sweep_started_at
            # Cosine easing has zero velocity at each reversal, avoiding the hard
            # corners and request-sized steps of the old browser triangle wave.
            phase = 0.5 - 0.5 * math.cos(math.tau * elapsed / VEHICLE_SWEEP_PERIOD_S)
            for signal, (minimum, maximum) in VEHICLE_SWEEP_RANGES.items():
                value = minimum + (maximum - minimum) * phase
                if signal is VehicleSignal.RPM:
                    value = round(value)
                self._set(signal, value)
        return tuple(self.active.values())

    def _set(self, signal: VehicleSignal, value: int | float) -> RoutedCanFrame:
        spec = VEHICLE_SIGNALS[signal]
        network = self.speed_network if signal is VehicleSignal.SPEED else spec.network
        routed = RoutedCanFrame(network, spec.encode(value))
        self.active[signal] = routed
        return routed
