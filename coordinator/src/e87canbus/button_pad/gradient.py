"""Shared direction and geometry for button-pad gradient effects."""

from enum import IntEnum

from e87canbus.protocol.can import BUTTON_PAD_GRADIENT_DIRECTION_NORTH_WEST_TO_SOUTH_EAST

BUTTON_PAD_COLUMNS = 4


class GradientDirection(IntEnum):
    """Wire values accepted by travelling-gradient tracks."""

    NORTH_WEST_TO_SOUTH_EAST = BUTTON_PAD_GRADIENT_DIRECTION_NORTH_WEST_TO_SOUTH_EAST


def gradient_coordinate(direction: GradientDirection, button_index: int) -> tuple[int, int]:
    """Return a button's position and inclusive maximum along ``direction``."""

    if not 0 <= button_index < BUTTON_PAD_COLUMNS * BUTTON_PAD_COLUMNS:
        raise ValueError("button index must identify the 4×4 button pad")
    if direction is GradientDirection.NORTH_WEST_TO_SOUTH_EAST:
        row, column = divmod(button_index, BUTTON_PAD_COLUMNS)
        return row + column, (BUTTON_PAD_COLUMNS - 1) * 2
    raise ValueError("unsupported button-pad gradient direction")
