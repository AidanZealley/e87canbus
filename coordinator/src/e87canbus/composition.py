"""Explicit live and simulated controller construction."""

from __future__ import annotations

import time
from collections.abc import Callable

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import AppConfig, CanNetwork, default_config, simulator_config
from e87canbus.device import DeviceSource
from e87canbus.live import LiveControllerRuntime
from e87canbus.service import ControllerMode, ControllerService
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.runtime import SimulatedControllerRuntime


def build_live_controller_service(
    *,
    config: AppConfig | None = None,
    button_pad_source: DeviceSource | None = None,
    tx_grants: frozenset[CanNetwork] = frozenset(),
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
) -> ControllerService:
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
        item.network
        for item in selected_config.can_networks
        if item.enabled and item.tx_enabled
    )
    unused_grants = tx_grants - configured_tx
    if unused_grants:
        unused = ", ".join(sorted(network.value for network in unused_grants))
        raise ValueError(f"live CAN TX grant has no enabled transmitter: {unused}")

    return ControllerService(
        LiveControllerRuntime(
            selected_config,
            button_pad_source=selected_button_pad,
            tx_grants=tx_grants,
            bus_factory=socketcan_factory,
            clock=clock,
        ),
        mode=ControllerMode.LIVE,
        clock=clock,
    )


def build_simulated_controller_service(
    *,
    config: AppConfig | None = None,
    button_pad_source: DeviceSource | None = None,
    clock: Callable[[], float] = time.monotonic,
    steering_controller_factory: Callable[
        [float, Callable[[], float]], SimulatedSteeringController
    ] = SimulatedSteeringController,
) -> ControllerService:
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
            steering_controller_factory=steering_controller_factory,
        ),
        mode=ControllerMode.SIMULATED,
        clock=clock,
    )


def _validate_networks(config: AppConfig) -> None:
    networks = [item.network for item in config.can_networks]
    if len(networks) != len(set(networks)):
        raise ValueError("each CAN network may be configured at most once")


def _network_enabled(config: AppConfig, network: CanNetwork) -> bool:
    return any(item.network is network and item.enabled for item in config.can_networks)
