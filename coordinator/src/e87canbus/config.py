"""Typed configuration boundary for coordinator and simulator composition."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import StrEnum

from e87canbus.protocol.generated import CAN_ID_BUTTON_EVENT, CAN_ID_LED_SNAPSHOT


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
    button_event: int = CAN_ID_BUTTON_EVENT
    led_snapshot: int = CAN_ID_LED_SNAPSHOT


@dataclass(frozen=True)
class SteeringConfig:
    manual_level_count: int = 8
    speed_timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if self.manual_level_count < 1:
            raise ValueError("manual_level_count must be positive")
        if not math.isfinite(self.speed_timeout_s) or self.speed_timeout_s <= 0:
            raise ValueError("speed_timeout_s must be finite and positive")


@dataclass(frozen=True)
class EngineTelemetryConfig:
    timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_s) or self.timeout_s <= 0:
            raise ValueError("engine telemetry timeout must be finite and positive")


@dataclass(frozen=True)
class PlaceholderBmwIds:
    """Unverified candidate IDs from project context, not replay constants."""

    possible_fcan_speed_id: int = 0x1A0
    possible_dsc_request_ids: tuple[int, ...] = (0x316, 0x399)


@dataclass(frozen=True)
class SimulationConfig:
    trace_capacity: int = 2_000
    steering_watchdog_timeout_s: float = 0.25
    websocket_send_timeout_s: float = 1.0

    def __post_init__(self) -> None:
        if self.trace_capacity < 1:
            raise ValueError("simulation trace capacity must be positive")
        if (
            not math.isfinite(self.steering_watchdog_timeout_s)
            or self.steering_watchdog_timeout_s <= 0
        ):
            raise ValueError("simulation steering watchdog timeout must be finite and positive")
        if (
            not math.isfinite(self.websocket_send_timeout_s)
            or self.websocket_send_timeout_s <= 0
        ):
            raise ValueError("simulation WebSocket send timeout must be finite and positive")


@dataclass(frozen=True)
class TxPolicyConfig:
    network_window_s: float = 1.0
    max_frames_per_network_window: int = 20

    def __post_init__(self) -> None:
        if not math.isfinite(self.network_window_s) or self.network_window_s <= 0:
            raise ValueError("TX policy window must be finite and positive")
        if self.max_frames_per_network_window < 1:
            raise ValueError("TX policy frame limit must be positive")


@dataclass(frozen=True)
class AppConfig:
    can_networks: tuple[CanNetworkConfig, ...] = field(default_factory=default_can_networks)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    custom_can_ids: CustomCanIds = field(default_factory=CustomCanIds)
    steering: SteeringConfig = field(default_factory=SteeringConfig)
    engine_telemetry: EngineTelemetryConfig = field(default_factory=EngineTelemetryConfig)
    placeholders: PlaceholderBmwIds = field(default_factory=PlaceholderBmwIds)
    tx_policy: TxPolicyConfig = field(default_factory=TxPolicyConfig)
    tick_interval_s: float = 0.1
    runtime_inbox_capacity: int = 1_024
    runtime_queue_latency_warning_s: float = 0.1
    runtime_command_timeout_s: float = 2.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.tick_interval_s) or self.tick_interval_s <= 0:
            raise ValueError("tick_interval_s must be finite and positive")
        if self.runtime_inbox_capacity < 1:
            raise ValueError("runtime_inbox_capacity must be positive")
        if (
            not math.isfinite(self.runtime_queue_latency_warning_s)
            or self.runtime_queue_latency_warning_s < 0
        ):
            raise ValueError("runtime_queue_latency_warning_s must be finite and non-negative")
        if (
            not math.isfinite(self.runtime_command_timeout_s)
            or self.runtime_command_timeout_s <= 0
        ):
            raise ValueError("runtime_command_timeout_s must be finite and positive")


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
