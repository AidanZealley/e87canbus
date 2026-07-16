"""Direct mapping between routed CAN frames and application values."""

from __future__ import annotations

from e87canbus.application.events import (
    ApplicationEvent,
    ButtonPressed,
    LedColour,
    SetButtonLeds,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.device import DeviceRole
from e87canbus.device_registry import RegistryHeartbeatObserved, RegistryHelloObserved
from e87canbus.protocol.can import (
    LedSnapshotPayload,
    RoutedCanFrame,
    decode_button_event,
    decode_heartbeat,
    decode_hello,
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

    def __init__(
        self,
        ids: CustomCanIds | None = None,
        *,
        button_input_enabled: bool = True,
    ) -> None:
        self.ids = ids or CustomCanIds()
        self.button_input_enabled = button_input_enabled

    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | RegistryHelloObserved | RegistryHeartbeatObserved | None:
        registry_observation = self._decode_registry(routed, observed_at)
        if registry_observation is not None:
            return registry_observation
        if (
            not self.button_input_enabled
            or routed.network is not CanNetwork.KCAN
            or routed.frame.arbitration_id != self.ids.button_event
        ):
            return None
        payload = decode_button_event(routed.frame, self.ids)
        assert payload is not None
        if not payload.pressed:
            return None
        return ButtonPressed(payload.button_index, observed_at)

    def _decode_registry(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> RegistryHelloObserved | RegistryHeartbeatObserved | None:
        if routed.network is not CanNetwork.KCAN:
            return None
        frame_id = routed.frame.arbitration_id
        for role, hello_id, heartbeat_id in (
            (
                DeviceRole.BUTTON_PAD,
                self.ids.button_pad_hello,
                self.ids.button_pad_heartbeat,
            ),
            (
                DeviceRole.SERVOTRONIC_CONTROLLER,
                self.ids.servotronic_controller_hello,
                self.ids.servotronic_controller_heartbeat,
            ),
            ):
            if frame_id == hello_id:
                hello_payload = decode_hello(routed.frame, hello_id)
                assert hello_payload is not None
                return RegistryHelloObserved(role, hello_payload, observed_at)
            if frame_id == heartbeat_id:
                heartbeat_payload = decode_heartbeat(routed.frame, heartbeat_id)
                assert heartbeat_payload is not None
                return RegistryHeartbeatObserved(role, heartbeat_payload, observed_at)
        return None

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
