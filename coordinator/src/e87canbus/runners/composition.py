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
from e87canbus.domain.device import DeviceRole, DeviceSource
from e87canbus.runners.live import LiveControllerRuntime
from e87canbus.runners.simulation.devices import SimulatedServotronicPeer
from e87canbus.runners.simulation.runtime import SimulatedControllerRuntime
from e87canbus.runners.simulation.vehicle_source import SyntheticVehicleSource
from e87canbus.service import ControllerService


def build_live_controller_service(
    *,
    config: AppConfig | None = None,
    button_pad_source: DeviceSource | None = None,
    servotronic_source: DeviceSource | None = None,
    tx_grants: frozenset[CanNetwork] = frozenset(),
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
    deployment: DeploymentSpec | None = None,
    profile_database_path: str | Path | None = None,
) -> ControllerService:
    selected_deployment = deployment or deployment_spec(DeploymentProfile.CAR)
    if selected_deployment.transport is not CanTransport.SOCKETCAN:
        raise ValueError("live controller requires a SocketCAN deployment profile")
    selected_config = config or default_config()
    _validate_networks(selected_config)
    kcan_enabled = _network_enabled(selected_config, CanNetwork.KCAN)
    selected_button_pad = button_pad_source or (
        DeviceSource.PHYSICAL if kcan_enabled else DeviceSource.DISABLED
    )
    if selected_button_pad is DeviceSource.EMULATED:
        raise ValueError("live composition cannot select an emulated ingress authority")
    if selected_button_pad is DeviceSource.PHYSICAL and not kcan_enabled:
        raise ValueError("physical button pad requires live SocketCAN K-CAN")

    configured_tx = frozenset(
        item.network for item in selected_config.can_networks if item.enabled and item.tx_enabled
    )
    unused_grants = tx_grants - configured_tx
    if unused_grants:
        unused = ", ".join(sorted(network.value for network in unused_grants))
        raise ValueError(f"live CAN TX grant has no enabled transmitter: {unused}")

    return ControllerService(
        LiveControllerRuntime(
            selected_config,
            button_pad_source=selected_button_pad,
            servotronic_source=servotronic_source,
            tx_grants=tx_grants,
            bus_factory=socketcan_factory,
            synthetic_vehicle=(
                SyntheticVehicleSource(selected_config.simulation.synthetic_speed_network)
                if selected_deployment.vehicle_source is VehicleSource.EMULATED
                else None
            ),
            clock=clock,
        ),
        deployment=selected_deployment,
        clock=clock,
        load_persisted_steering_curve=profile_database_path is not None,
    )


def build_simulated_controller_service(
    *,
    config: AppConfig | None = None,
    button_pad_source: DeviceSource | None = None,
    clock: Callable[[], float] = time.monotonic,
    servotronic_factory: Callable[
        [float, Callable[[], float]], SimulatedServotronicPeer
    ] = SimulatedServotronicPeer,
    deployment: DeploymentSpec | None = None,
) -> ControllerService:
    selected_deployment = deployment or deployment_spec(DeploymentProfile.SIMULATOR)
    if selected_deployment.transport is not CanTransport.IN_MEMORY:
        raise ValueError("simulated controller requires an in-memory deployment profile")
    selected_config = config or simulator_config()
    _validate_networks(selected_config)
    kcan_enabled = _network_enabled(selected_config, CanNetwork.KCAN)
    selected_button_pad = button_pad_source or (
        DeviceSource.EMULATED if kcan_enabled else DeviceSource.DISABLED
    )
    if selected_button_pad is DeviceSource.PHYSICAL:
        raise ValueError("physical button pad requires live SocketCAN K-CAN")
    kcan_tx_enabled = any(
        item.network is CanNetwork.KCAN and item.enabled and item.tx_enabled
        for item in selected_config.can_networks
    )
    if selected_button_pad is DeviceSource.EMULATED and not kcan_enabled:
        raise ValueError("emulated button pad requires simulated virtual K-CAN")
    if selected_button_pad is DeviceSource.EMULATED and not kcan_tx_enabled:
        raise ValueError("emulated button pad requires authorized simulated K-CAN output")

    return ControllerService(
        SimulatedControllerRuntime(
            config=selected_config,
            button_pad_source=selected_button_pad,
            clock=clock,
            servotronic_factory=servotronic_factory,
        ),
        deployment=selected_deployment,
        clock=clock,
    )


def build_controller_service(
    profile: DeploymentProfile,
    *,
    config: AppConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
    profile_database_path: str | Path | None = None,
) -> ControllerService:
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
            tx_networks=spec.tx_grants,
        )
        return build_simulated_controller_service(
            config=selected_config,
            button_pad_source=spec.device_source(DeviceRole.BUTTON_PAD),
            clock=clock,
            deployment=spec,
        )

    selected_config = configure_can_networks(
        selected_config,
        enabled_networks=spec.physical_networks,
        tx_networks=spec.tx_grants,
    )
    return build_live_controller_service(
        config=selected_config,
        button_pad_source=spec.device_source(DeviceRole.BUTTON_PAD),
        servotronic_source=spec.device_source(DeviceRole.SERVOTRONIC_CONTROLLER),
        tx_grants=spec.tx_grants,
        clock=clock,
        socketcan_factory=socketcan_factory,
        deployment=spec,
        profile_database_path=profile_database_path,
    )


def _validate_networks(config: AppConfig) -> None:
    networks = [item.network for item in config.can_networks]
    if len(networks) != len(set(networks)):
        raise ValueError("each CAN network may be configured at most once")


def _network_enabled(config: AppConfig, network: CanNetwork) -> bool:
    return any(item.network is network and item.enabled for item in config.can_networks)
