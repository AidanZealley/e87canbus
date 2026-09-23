"""Typed configuration boundary for coordinator and simulator composition."""

from __future__ import annotations

import math
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


def default_can_networks() -> tuple[CanNetworkConfig, ...]:
    """Return network settings in stable workbench/interface order."""

    return (
        CanNetworkConfig(CanNetwork.KCAN, "K-CAN", "kcan", 100_000),
        CanNetworkConfig(CanNetwork.PTCAN, "PT-CAN", "ptcan", 500_000),
        CanNetworkConfig(CanNetwork.FCAN, "F-CAN", "fcan", 500_000),
    )


@dataclass(frozen=True)
class SteeringConfig:
    manual_level_count: int = 11
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
    synthetic_speed_network: CanNetwork = CanNetwork.FCAN

    def __post_init__(self) -> None:
        if self.trace_capacity < 1:
            raise ValueError("simulation trace capacity must be positive")
        if not isinstance(self.synthetic_speed_network, CanNetwork):
            raise ValueError("simulation synthetic speed network must be a CAN network")


@dataclass(frozen=True)
class LivePublicationConfig:
    telemetry_hz: float = 25.0
    health_hz: float = 1.0
    client_queue_capacity: int = 64
    shutdown_timeout_s: float = 2.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.telemetry_hz) or self.telemetry_hz <= 0:
            raise ValueError("live telemetry rate must be finite and positive")
        if not math.isfinite(self.health_hz) or self.health_hz <= 0:
            raise ValueError("live health rate must be finite and positive")
        if self.client_queue_capacity < 1:
            raise ValueError("live client queue capacity must be positive")
        if not math.isfinite(self.shutdown_timeout_s) or self.shutdown_timeout_s <= 0:
            raise ValueError("live publisher shutdown timeout must be finite and positive")


@dataclass(frozen=True)
class AppConfig:
    can_networks: tuple[CanNetworkConfig, ...] = field(default_factory=default_can_networks)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    live_publication: LivePublicationConfig = field(default_factory=LivePublicationConfig)
    steering: SteeringConfig = field(default_factory=SteeringConfig)
    engine_telemetry: EngineTelemetryConfig = field(default_factory=EngineTelemetryConfig)
    placeholders: PlaceholderBmwIds = field(default_factory=PlaceholderBmwIds)
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
        if not math.isfinite(self.runtime_command_timeout_s) or self.runtime_command_timeout_s <= 0:
            raise ValueError("runtime_command_timeout_s must be finite and positive")


def default_config() -> AppConfig:
    return AppConfig()


def simulator_config() -> AppConfig:
    return default_config()


CANONICAL_NETWORK_ORDER = (CanNetwork.KCAN, CanNetwork.PTCAN, CanNetwork.FCAN)


class NetworkConfigError(ValueError):
    """Raised when network configuration parsing fails."""


def parse_network_names(value: str) -> frozenset[CanNetwork]:
    """Parse comma-separated network names into a frozenset of CanNetwork values.

    Accepts whitespace around commas. Rejects unknown names and duplicates.
    """
    if not value.strip():
        return frozenset()
    raw_names = [name.strip().lower() for name in value.split(",")]
    seen: set[str] = set()
    networks: set[CanNetwork] = set()
    for name in raw_names:
        if not name:
            continue
        if name in seen:
            raise NetworkConfigError(f"duplicate network name: {name}")
        seen.add(name)
        try:
            networks.add(CanNetwork(name))
        except ValueError:
            valid = ", ".join(n.value for n in CanNetwork)
            raise NetworkConfigError(f"unknown network name: {name}; valid: {valid}") from None
    return frozenset(networks)


def configure_can_networks(
    config: AppConfig,
    *,
    enabled_networks: frozenset[CanNetwork],
) -> AppConfig:
    """Select the enabled receive networks for a deployment."""
    networks = tuple(
        replace(item, enabled=item.network in enabled_networks) for item in config.can_networks
    )
    return replace(config, can_networks=networks)


def sorted_network_names(networks: frozenset[CanNetwork]) -> list[str]:
    """Return network names sorted in canonical order (kcan, ptcan, fcan)."""
    return [n.value for n in CANONICAL_NETWORK_ORDER if n in networks]
