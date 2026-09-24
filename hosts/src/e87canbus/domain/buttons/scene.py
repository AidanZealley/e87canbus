"""Resolve the selected profile into the appearance of every pad button."""

from __future__ import annotations

from dataclasses import dataclass

from e87canbus.domain.buttons.commands import button_command_is_active
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    SlotAnimation,
)
from e87canbus.domain.state import RGB_OFF, ApplicationState, Rgb

RESTING_BRIGHTNESS = 8


def resting_rgb(rgb: Rgb) -> Rgb:
    """Scale to the pad's resting level, rounding each channel to the nearest byte."""

    red, green, blue = rgb
    return (
        (red * RESTING_BRIGHTNESS + 127) // 255,
        (green * RESTING_BRIGHTNESS + 127) // 255,
        (blue * RESTING_BRIGHTNESS + 127) // 255,
    )


@dataclass(frozen=True)
class ResolvedButton:
    assigned: bool
    colour: Rgb
    animation: SlotAnimation | None


def resolve_button_pad(
    state: ApplicationState, profile: ActiveButtonProfile
) -> tuple[ResolvedButton, ...]:
    """Resolve all physical positions from coordinator state and the active profile."""

    buttons: list[ResolvedButton] = []
    for slot in profile.slots:
        if slot is None:
            buttons.append(ResolvedButton(False, RGB_OFF, None))
        elif button_command_is_active(state, slot.command):
            # active_colour is reserved and always None; colour is full brightness.
            buttons.append(ResolvedButton(True, slot.colour, slot.animation))
        else:
            buttons.append(ResolvedButton(True, resting_rgb(slot.colour), None))
    return tuple(buttons)
