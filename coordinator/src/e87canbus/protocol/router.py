"""Direct mapping between routed CAN frames and application values."""

from __future__ import annotations

from e87canbus.application.events import (
    ApplicationEvent,
    ButtonPressed,
    LedColour,
    SetButtonLeds,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    LedSnapshotPayload,
    RoutedCanFrame,
    decode_button_event,
    encode_led_snapshot,
)
from e87canbus.protocol.generated import (
    LED_COLOUR_AMBER,
    LED_COLOUR_BLUE,
    LED_COLOUR_GREEN,
    LED_COLOUR_OFF,
    LED_COLOUR_RED,
    LED_COLOUR_WHITE,
)

LED_COLOUR_CODES = {
    LedColour.OFF: LED_COLOUR_OFF,
    LedColour.RED: LED_COLOUR_RED,
    LedColour.GREEN: LED_COLOUR_GREEN,
    LedColour.BLUE: LED_COLOUR_BLUE,
    LedColour.AMBER: LED_COLOUR_AMBER,
    LedColour.WHITE: LED_COLOUR_WHITE,
}


class ProtocolRouter:
    """Decode verified inputs and encode effects without application bus choices."""

    def __init__(self, ids: CustomCanIds | None = None) -> None:
        self.ids = ids or CustomCanIds()

    def decode(
        self,
        routed: RoutedCanFrame,
        _observed_at: float,
    ) -> ApplicationEvent | None:
        if (
            routed.network is not CanNetwork.KCAN
            or routed.frame.arbitration_id != self.ids.button_event
        ):
            return None
        payload = decode_button_event(routed.frame, self.ids)
        assert payload is not None
        if not payload.pressed:
            return None
        return ButtonPressed(payload.button_index)

    def encode(self, effect: SetButtonLeds) -> RoutedCanFrame:
        return RoutedCanFrame(
            network=CanNetwork.KCAN,
            frame=encode_led_snapshot(
                LedSnapshotPayload(
                    tuple(LED_COLOUR_CODES[colour] for colour in effect.colours.colours)
                ),
                self.ids,
            ),
        )
