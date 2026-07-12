"""Symbolic button-to-action mappings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from e87canbus.application.events import ButtonState, MflButton, MflButtonEvent


class ActionType(StrEnum):
    MANUAL_ASSISTANCE_LEVEL_UP = "manual_assistance_level_up"
    MANUAL_ASSISTANCE_LEVEL_DOWN = "manual_assistance_level_down"
    HIGH_BEAM_STROBE = "high_beam_strobe"
    DSC_OFF_REQUEST = "dsc_off_request"


@dataclass(frozen=True)
class ButtonAction:
    action_type: ActionType


MFL_PRESS_MAPPINGS: dict[MflButton, ButtonAction] = {
    MflButton.VOLUME_UP: ButtonAction(ActionType.MANUAL_ASSISTANCE_LEVEL_UP),
    MflButton.VOLUME_DOWN: ButtonAction(ActionType.MANUAL_ASSISTANCE_LEVEL_DOWN),
    MflButton.PHONE_PICKUP: ButtonAction(ActionType.HIGH_BEAM_STROBE),
    MflButton.PHONE_HANGUP: ButtonAction(ActionType.DSC_OFF_REQUEST),
}

NEOTRELLIS_BUTTON_NOTES: dict[int, str] = {
    0: "placeholder: steering mode",
    1: "placeholder: assistance preset",
    2: "placeholder: strobe",
    3: "placeholder: DSC request",
}


def map_mfl_event(event: MflButtonEvent) -> ButtonAction | None:
    if event.state is not ButtonState.PRESSED:
        return None
    return MFL_PRESS_MAPPINGS.get(event.button)
