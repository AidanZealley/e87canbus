"""Validated physical/simulated adapter selection for the unified controller."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from e87canbus.adapters.socketcan import SocketCanBus
from e87canbus.config import AppConfig, CanNetwork, default_config, simulator_config
from e87canbus.device import DeviceAdapterSelection, DeviceRole, DeviceSource
from e87canbus.features.steering import CurveInterpolation
from e87canbus.live import LiveControllerRuntime
from e87canbus.runtime import SUPPORTED_STEERING_CURVE_INTERPOLATIONS
from e87canbus.service import (
    ControllerMode,
    ControllerRuntimeAdapter,
    ControllerService,
)
from e87canbus.simulation.devices import SimulatedSteeringController
from e87canbus.simulation.runtime import SimulatedControllerRuntime


class CanAdapterKind(StrEnum):
    SOCKETCAN = "socketcan"
    VIRTUAL = "virtual"
    DISABLED = "disabled"


class SteeringCapability(StrEnum):
    SIMULATED = "simulated"
    PHYSICAL_EVIDENCE_GATED = "physical-evidence-gated"
    ABSENT = "absent"


@dataclass(frozen=True)
class CanAdapterSelection:
    network: CanNetwork
    kind: CanAdapterKind


@dataclass(frozen=True)
class CompositionSelection:
    mode: ControllerMode
    can_adapters: tuple[CanAdapterSelection, ...]
    device_adapters: tuple[DeviceAdapterSelection, ...]
    steering: SteeringCapability
    tx_grants: frozenset[CanNetwork] = frozenset()

    def __post_init__(self) -> None:
        networks = [item.network for item in self.can_adapters]
        if len(networks) != len(set(networks)):
            raise ValueError("each CAN network must have exactly one selected adapter")

        for role in DeviceRole:
            selected = [item for item in self.device_adapters if item.role is role]
            if len(selected) != 1:
                raise ValueError(
                    f"device role {role.value} must have exactly one selected source; "
                    "duplicate ingress authority is not allowed"
                )

        if self.steering is SteeringCapability.PHYSICAL_EVIDENCE_GATED:
            raise ValueError("physical steering has no evidence-backed implementation or grant")
        if self.mode is ControllerMode.LIVE:
            if any(item.kind is CanAdapterKind.VIRTUAL for item in self.can_adapters):
                raise ValueError("live composition cannot select simulation-only CAN decoding")
            if any(
                item.source is DeviceSource.EMULATED for item in self.device_adapters
            ):
                raise ValueError("live composition cannot select an emulated ingress authority")
            if self.steering is not SteeringCapability.ABSENT:
                raise ValueError("live composition has no physical steering capability")
        else:
            if any(item.kind is CanAdapterKind.SOCKETCAN for item in self.can_adapters):
                raise ValueError("simulated composition cannot select SocketCAN")
            if self.steering is not SteeringCapability.SIMULATED:
                raise ValueError("simulated composition requires the simulated steering adapter")

        by_network = {item.network: item.kind for item in self.can_adapters}
        button_source = self.device_source(DeviceRole.BUTTON_PAD)
        if button_source is DeviceSource.PHYSICAL and (
            self.mode is not ControllerMode.LIVE
            or by_network.get(CanNetwork.KCAN) is not CanAdapterKind.SOCKETCAN
        ):
            raise ValueError("physical button pad requires live SocketCAN K-CAN")
        if button_source is DeviceSource.EMULATED and (
            self.mode is not ControllerMode.SIMULATED
            or by_network.get(CanNetwork.KCAN) is not CanAdapterKind.VIRTUAL
        ):
            raise ValueError("emulated button pad requires simulated virtual K-CAN")
        if (
            button_source is DeviceSource.EMULATED
            and CanNetwork.KCAN not in self.tx_grants
        ):
            raise ValueError(
                "emulated button pad requires authorized simulated K-CAN output"
            )

    def device_source(self, role: DeviceRole) -> DeviceSource:
        return next(item.source for item in self.device_adapters if item.role is role)


def live_selection(config: AppConfig | None = None) -> CompositionSelection:
    selected = config or default_config()
    kcan_enabled = any(
        item.network is CanNetwork.KCAN and item.enabled for item in selected.can_networks
    )
    return CompositionSelection(
        mode=ControllerMode.LIVE,
        can_adapters=tuple(
            CanAdapterSelection(
                item.network,
                CanAdapterKind.SOCKETCAN if item.enabled else CanAdapterKind.DISABLED,
            )
            for item in selected.can_networks
        ),
        device_adapters=(
            DeviceAdapterSelection(
                DeviceRole.BUTTON_PAD,
                DeviceSource.PHYSICAL if kcan_enabled else DeviceSource.DISABLED,
            ),
        ),
        steering=SteeringCapability.ABSENT,
    )


def simulated_selection(config: AppConfig | None = None) -> CompositionSelection:
    selected = config or simulator_config()
    kcan_enabled = any(
        item.network is CanNetwork.KCAN and item.enabled for item in selected.can_networks
    )
    return CompositionSelection(
        mode=ControllerMode.SIMULATED,
        can_adapters=tuple(
            CanAdapterSelection(
                item.network,
                CanAdapterKind.VIRTUAL if item.enabled else CanAdapterKind.DISABLED,
            )
            for item in selected.can_networks
        ),
        device_adapters=(
            DeviceAdapterSelection(
                DeviceRole.BUTTON_PAD,
                DeviceSource.EMULATED if kcan_enabled else DeviceSource.DISABLED,
            ),
        ),
        steering=SteeringCapability.SIMULATED,
        tx_grants=frozenset(
            item.network for item in selected.can_networks if item.enabled and item.tx_enabled
        ),
    )


def build_controller_service(
    mode: ControllerMode,
    *,
    config: AppConfig | None = None,
    selection: CompositionSelection | None = None,
    clock: Callable[[], float] = time.monotonic,
    socketcan_factory: Callable[[str], SocketCanBus] = SocketCanBus,
    steering_controller_factory: Callable[
        [float, Callable[[], float]], SimulatedSteeringController
    ] = SimulatedSteeringController,
    supported_steering_curve_interpolations: tuple[CurveInterpolation, ...] = (
        SUPPORTED_STEERING_CURVE_INTERPOLATIONS
    ),
) -> ControllerService:
    selected_config = config or (
        simulator_config() if mode is ControllerMode.SIMULATED else default_config()
    )
    selected = selection or (
        simulated_selection(selected_config)
        if mode is ControllerMode.SIMULATED
        else live_selection(selected_config)
    )
    if selected.mode is not mode:
        raise ValueError("composition selection mode does not match requested mode")
    _validate_network_selection(selected_config, selected)

    if mode is ControllerMode.SIMULATED:
        button_source = selected.device_source(DeviceRole.BUTTON_PAD)
        runtime: ControllerRuntimeAdapter = SimulatedControllerRuntime(
            config=selected_config,
            button_pad_source=button_source,
            clock=clock,
            steering_controller_factory=steering_controller_factory,
            supported_steering_curve_interpolations=(
                supported_steering_curve_interpolations
            ),
        )
    else:
        runtime = LiveControllerRuntime(
            selected_config,
            button_pad_source=selected.device_source(DeviceRole.BUTTON_PAD),
            tx_grants=selected.tx_grants,
            bus_factory=socketcan_factory,
            clock=clock,
        )
    return ControllerService(runtime, mode=mode, clock=clock)


def _validate_network_selection(
    config: AppConfig,
    selection: CompositionSelection,
) -> None:
    configured_networks = [item.network for item in config.can_networks]
    if len(configured_networks) != len(set(configured_networks)):
        raise ValueError("each CAN network may be configured at most once")
    by_network = {item.network: item for item in selection.can_adapters}
    if set(by_network) != set(configured_networks):
        raise ValueError("CAN adapter selections must match configured networks exactly")
    for configured in config.can_networks:
        selected = by_network.get(configured.network)
        expected_disabled = not configured.enabled
        if selected is None:
            raise ValueError(f"missing CAN adapter selection for {configured.network.value}")
        if expected_disabled != (selected.kind is CanAdapterKind.DISABLED):
            raise ValueError(
                f"CAN adapter selection disagrees with enabled state for "
                f"{configured.network.value}"
            )
        if configured.tx_enabled and configured.network not in selection.tx_grants:
            raise ValueError(
                f"CAN TX for {configured.network.value} requires an explicit network grant"
            )
        if configured.network in selection.tx_grants and not configured.tx_enabled:
            raise ValueError(
                f"CAN TX grant for {configured.network.value} has no enabled transmitter"
            )
