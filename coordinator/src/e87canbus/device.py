"""Repository-owned custom-device composition and projection contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DeviceRole(StrEnum):
    BUTTON_PAD = "button_pad"


class DeviceSource(StrEnum):
    PHYSICAL = "physical"
    EMULATED = "emulated"
    OBSERVER = "observer"
    DISABLED = "disabled"


@dataclass(frozen=True)
class DeviceProjection:
    """Desired controller output and evidence-backed device observation."""

    id: DeviceRole
    label: str
    source_mode: DeviceSource
    connected: bool | None
    last_seen_monotonic_s: float | None
    desired_led_colours: tuple[int, ...]
    observed_led_colours: tuple[int, ...] | None
    last_output_fault: str | None
