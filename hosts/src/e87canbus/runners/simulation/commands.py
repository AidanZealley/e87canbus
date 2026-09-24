"""Closed commands accepted by the simulated vehicle runtime."""

from dataclasses import dataclass

from e87canbus.runners.simulation.signals import VehicleSignal


@dataclass(frozen=True)
class SetVehicleSignal:
    signal: VehicleSignal
    value: int | float


@dataclass(frozen=True)
class SilenceVehicleSignal:
    signal: VehicleSignal


@dataclass(frozen=True)
class SetVehicleSweep:
    enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise ValueError("vehicle sweep enabled must be a boolean")


@dataclass(frozen=True)
class ResetSimulation:
    pass


SimulationCommand = (
    SetVehicleSignal | SilenceVehicleSignal | SetVehicleSweep | ResetSimulation
)
