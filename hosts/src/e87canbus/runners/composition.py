"""Explicit live and simulated controller construction."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import (
    AppConfig,
    CanNetwork,
    configure_can_networks,
    default_config,
    simulator_config,
)
from e87canbus.deployment import (
    CanTransport,
    DeploymentProfile,
    DeploymentSpec,
    VehicleSource,
    deployment_spec,
)
from e87canbus.runners.live import LiveControllerRuntime
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource
from e87canbus.service import ControllerLoop


def build_live_controller_loop(
    *,
    config: AppConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
    deployment: DeploymentSpec | None = None,
    profile_database_path: str | Path | None = None,
) -> ControllerLoop:
    selected_deployment = deployment or deployment_spec(DeploymentProfile.CAR)
    if selected_deployment.transport is not CanTransport.SOCKETCAN:
        raise ValueError("live controller requires a SocketCAN deployment profile")
    selected_config = config or default_config()
    _validate_networks(selected_config)
    return ControllerLoop(
        LiveControllerRuntime(
            selected_config,
            bus_factory=socketcan_factory,
            synthetic_vehicle=(
                SyntheticVehicleSource(
                    selected_config.simulation.synthetic_speed_network,
                    clock,
                )
                if selected_deployment.vehicle_source is VehicleSource.EMULATED
                else None
            ),
            clock=clock,
        ),
        deployment=selected_deployment,
        clock=clock,
        load_persisted_steering_curve=profile_database_path is not None,
        load_persisted_button_profile=profile_database_path is not None,
    )


def build_simulated_controller_loop(
    *,
    config: AppConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
    deployment: DeploymentSpec | None = None,
    profile_database_path: str | Path | None = None,
) -> ControllerLoop:
    selected_deployment = deployment or deployment_spec(DeploymentProfile.SIMULATOR)
    if selected_deployment.transport is not CanTransport.IN_MEMORY:
        raise ValueError("simulated controller requires an in-memory deployment profile")
    selected_config = config or simulator_config()
    _validate_networks(selected_config)
    return ControllerLoop(
        SimulatedControllerRuntime(
            config=selected_config,
            clock=clock,
        ),
        deployment=selected_deployment,
        clock=clock,
        load_persisted_button_profile=profile_database_path is not None,
    )


def build_controller_loop(
    profile: DeploymentProfile,
    *,
    config: AppConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
    profile_database_path: str | Path | None = None,
) -> ControllerLoop:
    """Build one of the closed operator-facing deployment profiles."""

    spec = deployment_spec(profile)
    selected_config = config or default_config()
    if profile is DeploymentProfile.BENCH:
        selected_config = replace(
            selected_config,
            simulation=replace(
                selected_config.simulation,
                synthetic_speed_network=CanNetwork.KCAN,
            ),
        )
    if spec.transport is CanTransport.IN_MEMORY:
        selected_config = configure_can_networks(
            selected_config,
            enabled_networks=frozenset(CanNetwork),
        )
        return build_simulated_controller_loop(
            config=selected_config,
            clock=clock,
            deployment=spec,
            profile_database_path=profile_database_path,
        )

    selected_config = configure_can_networks(
        selected_config,
        enabled_networks=spec.physical_networks,
    )
    return build_live_controller_loop(
        config=selected_config,
        clock=clock,
        socketcan_factory=socketcan_factory,
        deployment=spec,
        profile_database_path=profile_database_path,
    )


def _validate_networks(config: AppConfig) -> None:
    networks = [item.network for item in config.can_networks]
    if len(networks) != len(set(networks)):
        raise ValueError("each CAN network may be configured at most once")
