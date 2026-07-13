"""Central mapping between routed CAN frames and application-level values."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from e87canbus.application.controller import ApplicationEvent, ApplicationOutput
from e87canbus.application.events import (
    ButtonLedCommand,
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    LED_AMBER,
    LED_BLUE,
    LED_GREEN,
    LED_OFF,
    LED_RED,
    LED_WHITE,
    CanFrame,
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

FrameDecoder: TypeAlias = Callable[[CanFrame], ApplicationEvent]
OutputEncoder: TypeAlias = Callable[[ApplicationOutput], RoutedCanFrame]


class ProtocolRouter:
    """Decode by network and ID, and encode outputs without feature-layer bus choices."""

    def __init__(self, ids: CustomCanIds | None = None) -> None:
        self.ids = ids or CustomCanIds()
        self._decoders: dict[tuple[CanNetwork, int], FrameDecoder] = {
            (CanNetwork.KCAN, self.ids.button_event): self._decode_button_event,
        }
        self._encoders: dict[type[object], OutputEncoder] = {
            ButtonLedCommand: self._encode_button_led_command,
        }

    def decode(self, routed: RoutedCanFrame) -> ApplicationEvent | None:
        decoder = self._decoders.get((routed.network, routed.frame.arbitration_id))
        if decoder is None:
            return None
        return decoder(routed.frame)

    def register_decoder(
        self,
        network: CanNetwork,
        arbitration_id: int,
        decoder: FrameDecoder,
    ) -> None:
        """Register a future verified decoder for one network-specific CAN ID."""

        self._decoders[(network, arbitration_id)] = decoder

    def encode(self, output: ApplicationOutput) -> RoutedCanFrame:
        encoder = self._encoders.get(type(output))
        if encoder is None:
            raise ValueError(f"no CAN encoder registered for {type(output).__name__}")
        return encoder(output)

    def _decode_button_event(self, frame: CanFrame) -> NeoTrellisButtonEvent:
        payload = decode_button_event(frame, self.ids)
        assert payload is not None
        return NeoTrellisButtonEvent(
            button_index=payload.button_index,
            state=ButtonState.PRESSED if payload.pressed else ButtonState.RELEASED,
        )

    def _encode_button_led_command(self, output: ApplicationOutput) -> RoutedCanFrame:
        assert isinstance(output, ButtonLedCommand)
        return RoutedCanFrame(
            network=CanNetwork.KCAN,
            frame=encode_led_update(
                LedUpdatePayload(
                    button_index=output.button_index,
                    colour_code=LED_COLOUR_CODES[output.colour],
                ),
                self.ids,
            ),
        )
