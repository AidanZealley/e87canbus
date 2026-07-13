"""Typed configuration boundary for coordinator and simulator composition."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum


class CanNetwork(StrEnum):
    """Stable logical identities for the three physical BMW CAN networks."""

    KCAN = "kcan"
    PTCAN = "ptcan"
    FCAN = "fcan"


@dataclass(frozen=True)
class CanNetworkConfig:
    network: CanNetwork
    label: str
    interface: str
    bitrate: int
    enabled: bool = True
    tx_enabled: bool = False


def default_can_networks() -> tuple[CanNetworkConfig, ...]:
    """Return network settings in stable workbench/interface order."""

    return (
        CanNetworkConfig(CanNetwork.KCAN, "K-CAN", "can0", 100_000),
        CanNetworkConfig(CanNetwork.PTCAN, "PT-CAN", "can1", 500_000),
        CanNetworkConfig(CanNetwork.FCAN, "F-CAN", "can2", 500_000),
    )


@dataclass(frozen=True)
class CustomCanIds:
    button_event: int = 0x700
    led_update: int = 0x701


@dataclass(frozen=True)
class SteeringConfig:
    manual_level_count: int = 8
    min_target_current_ma: int = 200
    max_target_current_ma: int = 800
    auto_assistance_curve: tuple[tuple[float, float], ...] = (
        (0.0, 800.0),
        (30.0, 600.0),
        (100.0, 200.0),
    )
    speed_timeout_s: float = 1.0


@dataclass(frozen=True)
class PlaceholderBmwIds:
    """Unverified candidate IDs from project context, not replay constants."""

    possible_fcan_speed_id: int = 0x1A0
    possible_dsc_request_ids: tuple[int, ...] = (0x316, 0x399)


@dataclass(frozen=True)
class SimulationConfig:
    trace_capacity: int = 2_000


@dataclass(frozen=True)
class TxPolicyConfig:
    network_window_s: float = 1.0
    max_frames_per_network_window: int = 20

    def __post_init__(self) -> None:
        if self.network_window_s <= 0:
            raise ValueError("TX policy window must be positive")
        if self.max_frames_per_network_window < 1:
            raise ValueError("TX policy frame limit must be positive")


@dataclass(frozen=True)
class AppConfig:
    can_networks: tuple[CanNetworkConfig, ...] = field(default_factory=default_can_networks)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    custom_can_ids: CustomCanIds = field(default_factory=CustomCanIds)
    steering: SteeringConfig = field(default_factory=SteeringConfig)
    placeholders: PlaceholderBmwIds = field(default_factory=PlaceholderBmwIds)
    tx_policy: TxPolicyConfig = field(default_factory=TxPolicyConfig)
    tick_interval_s: float = 0.1
    runtime_inbox_capacity: int = 1_024
    runtime_queue_latency_warning_s: float = 0.1

    def __post_init__(self) -> None:
        if self.runtime_inbox_capacity < 1:
            raise ValueError("runtime_inbox_capacity must be positive")
        if self.runtime_queue_latency_warning_s < 0:
            raise ValueError("runtime_queue_latency_warning_s must be non-negative")


def default_config() -> AppConfig:
    return AppConfig()


def simulator_config() -> AppConfig:
    """Enable the provisional project protocol for the isolated simulator."""

    config = default_config()
    networks = tuple(
        replace(item, tx_enabled=item.network is CanNetwork.KCAN)
        for item in config.can_networks
    )
    return replace(config, can_networks=networks)
