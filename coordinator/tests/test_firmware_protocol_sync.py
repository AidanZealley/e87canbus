import re
from pathlib import Path

from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import (
    BUTTON_PRESSED,
    BUTTON_RELEASED,
    LED_AMBER,
    LED_BLUE,
    LED_GREEN,
    LED_OFF,
    LED_RED,
    LED_WHITE,
)


def constants_from_header(text: str) -> dict[str, int]:
    matches = re.findall(
        r"^\s*static const\s+.+?\s+([A-Z][A-Z0-9_]*)\s*=\s*(0[xX][0-9a-fA-F]+|\d+)\s*;",
        text,
        flags=re.MULTILINE,
    )
    return {name: int(value, 0) for name, value in matches}


def test_button_pad_firmware_constants_match_protocol() -> None:
    header_path = (
        Path(__file__).resolve().parents[2]
        / "devices"
        / "button-pad"
        / "include"
        / "can_ids.h"
    )
    constants = constants_from_header(header_path.read_text())
    ids = CustomCanIds()

    assert constants["CAN_ID_BUTTON_EVENT"] == ids.button_event
    assert constants["CAN_ID_LED_UPDATE"] == ids.led_update
    assert constants["BUTTON_PRESSED"] == BUTTON_PRESSED
    assert constants["BUTTON_RELEASED"] == BUTTON_RELEASED
    assert constants["LED_COLOUR_OFF"] == LED_OFF
    assert constants["LED_COLOUR_RED"] == LED_RED
    assert constants["LED_COLOUR_GREEN"] == LED_GREEN
    assert constants["LED_COLOUR_BLUE"] == LED_BLUE
    assert constants["LED_COLOUR_AMBER"] == LED_AMBER
    assert constants["LED_COLOUR_WHITE"] == LED_WHITE
