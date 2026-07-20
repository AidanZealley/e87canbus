"""Named, closed deployment compositions selected by operators."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.config import CanNetwork
from e87canbus.device import DeviceRole, DeviceSource


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
    """Amount of the simulation-owned HTTP surface installed for a profile."""

    NONE = "none"
    VEHICLE = "vehicle"
    FULL = "full"


@dataclass(frozen=True)
class DeploymentSpec:
    profile: DeploymentProfile
    transport: CanTransport
    device_sources: tuple[tuple[DeviceRole, DeviceSource], ...]
    vehicle_source: VehicleSource
    physical_networks: frozenset[CanNetwork]
    tx_grants: frozenset[CanNetwork]
    simulation_api: SimulationApiScope

    def __post_init__(self) -> None:
        roles = tuple(role for role, _source in self.device_sources)
        if len(roles) != len(set(roles)):
            raise ValueError("deployment device roles must be unique")
        if not self.tx_grants.issubset(self.physical_networks) and (
            self.transport is CanTransport.SOCKETCAN
        ):
            raise ValueError("SocketCAN TX grants require an enabled physical network")
        expected = _PROFILE_FIELDS[self.profile]
        actual = (
            self.transport,
            self.device_sources,
            self.vehicle_source,
            self.physical_networks,
            self.tx_grants,
            self.simulation_api,
        )
        if actual != expected:
            raise ValueError(
                f"deployment profile {self.profile.value} must use its closed composition"
            )

    def device_source(self, role: DeviceRole) -> DeviceSource:
        return dict(self.device_sources).get(role, DeviceSource.DISABLED)


def deployment_spec(profile: DeploymentProfile) -> DeploymentSpec:
    """Resolve one supported profile without permitting arbitrary combinations."""

    fields = _PROFILE_FIELDS[profile]
    return DeploymentSpec(profile, *fields)


_PROFILE_FIELDS = {
    DeploymentProfile.CAR: (
        CanTransport.SOCKETCAN,
        (
            (DeviceRole.BUTTON_PAD, DeviceSource.PHYSICAL),
            (DeviceRole.SERVOTRONIC_CONTROLLER, DeviceSource.PHYSICAL),
        ),
        VehicleSource.PHYSICAL,
        frozenset(CanNetwork),
        # Live vehicle transmission remains denied until separately validated.
        frozenset(),
        SimulationApiScope.NONE,
    ),
    DeploymentProfile.BENCH: (
        CanTransport.SOCKETCAN,
        (
            (DeviceRole.BUTTON_PAD, DeviceSource.PHYSICAL),
            (DeviceRole.SERVOTRONIC_CONTROLLER, DeviceSource.PHYSICAL),
        ),
        VehicleSource.EMULATED,
        frozenset({CanNetwork.KCAN}),
        frozenset({CanNetwork.KCAN}),
        SimulationApiScope.VEHICLE,
    ),
    DeploymentProfile.SIMULATOR: (
        CanTransport.IN_MEMORY,
        (
            (DeviceRole.BUTTON_PAD, DeviceSource.EMULATED),
            (DeviceRole.SERVOTRONIC_CONTROLLER, DeviceSource.EMULATED),
        ),
        VehicleSource.EMULATED,
        frozenset(),
        frozenset({CanNetwork.KCAN}),
        SimulationApiScope.FULL,
    ),
}
