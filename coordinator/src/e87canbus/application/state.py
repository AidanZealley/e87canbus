"""Small explicit runtime state container."""

from __future__ import annotations

from dataclasses import dataclass, field

from e87canbus.application.events import SteeringMode
from e87canbus.config import CanNetwork


def _empty_can_health() -> dict[CanNetwork, float | None]:
    return {network: None for network in CanNetwork}


@dataclass
class CanHealth:
    latest_rx_monotonic_s: dict[CanNetwork, float | None] = field(
        default_factory=_empty_can_health
    )

    def record_receive(self, network: CanNetwork, monotonic_s: float) -> None:
        self.latest_rx_monotonic_s[network] = monotonic_s


@dataclass
class RuntimeState:
    vehicle_speed_kph: float = 0.0
    steering_mode: SteeringMode = SteeringMode.AUTO
    manual_assistance_level: int = 0
    maximum_assistance_active: bool = False
    can_health: CanHealth = field(default_factory=CanHealth)

    def set_speed(self, speed_kph: float) -> None:
        self.vehicle_speed_kph = max(0.0, speed_kph)

    def set_manual_assistance_level(self, level: int, level_count: int) -> None:
        self.manual_assistance_level = min(max(level, 0), level_count - 1)
