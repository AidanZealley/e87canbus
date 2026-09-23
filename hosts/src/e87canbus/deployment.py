"""Named, closed deployment compositions selected by operators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.config import CanNetwork


class DeploymentProfile(StrEnum):
    CAR = "car"
    BENCH = "bench"
    SIMULATOR = "simulator"


class CanTransport(StrEnum):
    SOCKETCAN = "socketcan"
    IN_MEMORY = "in_memory"


class VehicleSource(StrEnum):
    PHYSICAL = "physical"
    EMULATED = "emulated"


class SimulationApiScope(StrEnum):
    NONE = "none"
    VEHICLE = "vehicle"
    FULL = "full"


@dataclass(frozen=True)
class DeploymentSpec:
    profile: DeploymentProfile
    transport: CanTransport
    vehicle_source: VehicleSource
    physical_networks: frozenset[CanNetwork]
    simulation_api: SimulationApiScope

    def __post_init__(self) -> None:
        if (
            self.transport,
            self.vehicle_source,
            self.physical_networks,
            self.simulation_api,
        ) != _PROFILE_FIELDS[self.profile]:
            raise ValueError(
                f"deployment profile {self.profile.value} must use its closed composition"
            )


def deployment_spec(profile: DeploymentProfile) -> DeploymentSpec:
    return DeploymentSpec(profile, *_PROFILE_FIELDS[profile])


_PROFILE_FIELDS = {
    DeploymentProfile.CAR: (
        CanTransport.SOCKETCAN,
        VehicleSource.PHYSICAL,
        frozenset(CanNetwork),
        SimulationApiScope.NONE,
    ),
    DeploymentProfile.BENCH: (
        CanTransport.SOCKETCAN,
        VehicleSource.EMULATED,
        frozenset(CanNetwork),
        SimulationApiScope.VEHICLE,
    ),
    DeploymentProfile.SIMULATOR: (
        CanTransport.IN_MEMORY,
        VehicleSource.EMULATED,
        frozenset(),
        SimulationApiScope.FULL,
    ),
}
