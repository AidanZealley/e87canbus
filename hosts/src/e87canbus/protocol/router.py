"""Direct mapping between routed CAN frames and application values."""

from __future__ import annotations

from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.domain.devices.catalogue import DeviceRole
from e87canbus.domain.devices.registry import RegistryHeartbeatObserved, RegistryHelloObserved
from e87canbus.domain.events import (
    ApplicationEvent,
)
from e87canbus.protocol.can import (
    DeviceWelcomeAckPayload,
    RoutedCanFrame,
    decode_heartbeat,
    decode_hello,
    encode_welcome_ack,
)

DecodedProtocolEvent = ApplicationEvent | RegistryHelloObserved | RegistryHeartbeatObserved


class ProtocolRouter:
    """Decode verified inputs and encode effects without application bus choices."""

    def __init__(
        self,
        ids: CustomCanIds | None = None,
    ) -> None:
        self.ids = ids or CustomCanIds()

    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> DecodedProtocolEvent | None:
        registry_observation = self._decode_registry(routed, observed_at)
        if registry_observation is not None:
            return registry_observation
        return None

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
                DeviceRole.SERVOTRONIC_CONTROLLER,
                self.ids.servotronic_controller_hello,
                self.ids.servotronic_controller_heartbeat,
            ),
        ):
            if frame_id == hello_id:
                hello_payload = decode_hello(routed.frame, hello_id)
                if hello_payload is not None:
                    return RegistryHelloObserved(role, hello_payload, observed_at)
            if frame_id == heartbeat_id:
                heartbeat_payload = decode_heartbeat(routed.frame, heartbeat_id)
                if heartbeat_payload is not None:
                    return RegistryHeartbeatObserved(role, heartbeat_payload, observed_at)
        return None

    def encode_registry_ack(
        self,
        role: DeviceRole,
        acknowledgement: DeviceWelcomeAckPayload,
    ) -> RoutedCanFrame:
        arbitration_id = self.ids.servotronic_controller_welcome_ack
        return RoutedCanFrame(
            CanNetwork.KCAN,
            encode_welcome_ack(acknowledgement, arbitration_id),
        )
