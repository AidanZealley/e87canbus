"""Build one vehicle-only in-memory simulation session."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from e87canbus.adapters.can_io import CanReceiver
from e87canbus.config import AppConfig, CanNetwork
from e87canbus.domain.buttons.profiles import ActiveButtonProfile
from e87canbus.domain.steering.curves import ActiveSteeringCurve
from e87canbus.kernel import CoordinatorKernel
from e87canbus.runners.simulation.bus import InMemoryCanNetwork
from e87canbus.runners.simulation.devices import SimulatedVehicleNode
from e87canbus.runners.simulation.protocol import SimulationProtocolRouter
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource


@dataclass(frozen=True)
class SimulationSession:
    pi_buses: dict[CanNetwork, CanReceiver]
    vehicle: SimulatedVehicleNode
    kernel: CoordinatorKernel


def build_session(
    config: AppConfig,
    clock: Callable[[], float],
    *,
    button_profile: ActiveButtonProfile | None,
    initial_steering_curve: ActiveSteeringCurve | None,
    button_profile_saved_revision: int | None = None,
) -> SimulationSession:
    networks = {network: InMemoryCanNetwork() for network in CanNetwork}
    pi_buses: dict[CanNetwork, CanReceiver] = {
        item.network: networks[item.network].create_bus("pi")
        for item in config.can_networks
        if item.enabled
    }
    vehicle_buses = {
        item.network: networks[item.network].create_bus("simulated-vehicle")
        for item in config.can_networks
    }
    vehicle = SimulatedVehicleNode(
        vehicle_buses, SyntheticVehicleSource(config.simulation.synthetic_speed_network, clock)
    )
    kernel = CoordinatorKernel(
        steering_config=config.steering,
        engine_telemetry_config=config.engine_telemetry,
        decoder=SimulationProtocolRouter(
            synthetic_speed_network=config.simulation.synthetic_speed_network
        ).decode,
        active_steering_curve=initial_steering_curve,
    )
    if button_profile is not None:
        kernel.configure_initial_button_profile(button_profile, button_profile_saved_revision)
    return SimulationSession(pi_buses, vehicle, kernel)
