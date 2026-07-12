"""Default configuration for the local-testable project scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CanInterfaces:
    kcan_interface: str = "can0"
    fcan_interface: str = "can1"


@dataclass(frozen=True)
class CanBitrates:
    kcan: int = 100_000
    fcan: int = 500_000


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


@dataclass(frozen=True)
class StrobeConfig:
    cycles: int = 5
    on_duration_s: float = 0.080
    off_duration_s: float = 0.080


@dataclass(frozen=True)
class PlaceholderBmwIds:
    """Unverified candidate IDs from project context, not replay constants."""

    possible_fcan_speed_id: int = 0x1A0
    possible_dsc_request_ids: tuple[int, ...] = (0x316, 0x399)


@dataclass(frozen=True)
class AppConfig:
    can_interfaces: CanInterfaces = field(default_factory=CanInterfaces)
    can_bitrates: CanBitrates = field(default_factory=CanBitrates)
    custom_can_ids: CustomCanIds = field(default_factory=CustomCanIds)
    steering: SteeringConfig = field(default_factory=SteeringConfig)
    strobe: StrobeConfig = field(default_factory=StrobeConfig)
    placeholders: PlaceholderBmwIds = field(default_factory=PlaceholderBmwIds)


def default_config() -> AppConfig:
    return AppConfig()

