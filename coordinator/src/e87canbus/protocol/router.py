"""Direct mapping between routed CAN frames and application values."""

from __future__ import annotations

from e87canbus.application.events import (
    ApplicationEffect,
    ApplicationEvent,
    ButtonPressed,
    LedColour,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    LED_AMBER,
    LED_BLUE,
    LED_GREEN,
    LED_OFF,
    LED_RED,
    LED_WHITE,
    LedUpdatePayload,
    RoutedCanFrame,
    decode_button_event,
    encode_led_update,
)

LED_COLOUR_CODES = {
    LedColour.OFF: LED_OFF,
    LedColour.RED: LED_RED,
    LedColour.GREEN: LED_GREEN,
    LedColour.BLUE: LED_BLUE,
    LedColour.AMBER: LED_AMBER,
    LedColour.WHITE: LED_WHITE,
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

    def encode(self, effect: ApplicationEffect) -> RoutedCanFrame:
        return RoutedCanFrame(
            network=CanNetwork.KCAN,
            frame=encode_led_update(
                LedUpdatePayload(
                    button_index=effect.button_index,
                    colour_code=LED_COLOUR_CODES[effect.colour],
                ),
                self.ids,
            ),
        )
