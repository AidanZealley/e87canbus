"""Simulated project CAN devices."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from e87canbus.can_io import CanEndpoint
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    LedUpdatePayload,
    decode_led_update,
    encode_button_event,
)

LOGGER = logging.getLogger(__name__)


@dataclass
class SimulatedNeoTrellisNode:
    """Simulation of the current Arduino NeoTrellis CAN firmware."""

    bus: CanEndpoint
    ids: CustomCanIds
    button_index: int = 0
    next_pressed: bool = True
    led_colours: dict[int, int] = field(default_factory=dict)

    def send_button_event(self, button_index: int, pressed: bool) -> CanFrame:
        frame = encode_button_event(
            ArduinoButtonEventPayload(
                button_index=button_index,
                pressed=pressed,
            ),
            self.ids,
        )
        self.bus.send(frame)
        return frame

    def send_next_button_event(self) -> CanFrame:
        frame = self.send_button_event(self.button_index, self.next_pressed)
        self.next_pressed = not self.next_pressed
        return frame

    def process_pending_led_updates(self) -> list[LedUpdatePayload]:
        updates: list[LedUpdatePayload] = []
        while True:
            frame = self.bus.receive(timeout_s=0)
            if frame is None:
                return updates

            update = self._decode_led_update(frame)
            if update is None:
                continue

            self.led_colours[update.button_index] = update.colour_code
            updates.append(update)

    def _decode_led_update(self, frame: CanFrame) -> LedUpdatePayload | None:
        try:
            return decode_led_update(frame, self.ids)
        except ValueError as exc:
            LOGGER.warning(
                "sim neotrellis ignored malformed led update: id=0x%03x data=%s error=%s",
                frame.arbitration_id,
                frame.data.hex(),
                exc,
            )
            return None


@dataclass
class SimulatedCar:
    """Placeholder car composition with one passive endpoint per BMW network."""

    buses: dict[CanNetwork, CanEndpoint]

    def drain_pending(self) -> int:
        drained = 0
        for network in CanNetwork:
            bus = self.buses.get(network)
            if bus is None:
                continue
            while bus.receive(timeout_s=0) is not None:
                drained += 1
        return drained


@dataclass
class SimulatedSteeringControllerNode:
    """K-CAN placeholder until a verified steering wire protocol exists."""

    bus: CanEndpoint

    def drain_pending(self) -> int:
        drained = 0
        while self.bus.receive(timeout_s=0) is not None:
            drained += 1
        return drained
