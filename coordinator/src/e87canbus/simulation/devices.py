"""Simulated project CAN devices."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.can_io import CanEndpoint
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    LedUpdatePayload,
    decode_led_update,
    encode_button_event,
)
from e87canbus.simulation.protocol import encode_simulated_speed

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
class SimulatedVehicleNode:
    """External simulation node with an explicitly synthetic speed message."""

    buses: dict[CanNetwork, CanEndpoint]
    speed_kph: float | None = None

    def set_speed(self, speed_kph: float) -> CanFrame:
        frame = encode_simulated_speed(speed_kph)
        self.speed_kph = speed_kph
        self.buses[CanNetwork.FCAN].send(frame)
        return frame

    def emit_speed(self) -> CanFrame | None:
        if self.speed_kph is None:
            return None
        frame = encode_simulated_speed(self.speed_kph)
        self.buses[CanNetwork.FCAN].send(frame)
        return frame

    def silence_speed(self) -> None:
        self.speed_kph = None

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
class SimulatedSteeringController:
    """Dimensionless actuator model with an independent command watchdog."""

    watchdog_timeout_s: float
    clock: Callable[[], float] = time.monotonic
    last_command: SetSteeringAssistance | None = None
    last_command_at: float | None = None
    commands: list[SetSteeringAssistance] = field(default_factory=list)

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.last_command = command
        self.last_command_at = self.clock()
        self.commands.append(command)

    @property
    def watchdog_timed_out(self) -> bool:
        return self.last_command_at is None or (
            self.clock() - self.last_command_at > self.watchdog_timeout_s
        )

    @property
    def effective_assistance(self) -> float:
        if self.watchdog_timed_out or self.last_command is None:
            return 0.0
        return self.last_command.assistance

    @property
    def last_command_reason(self) -> SteeringCommandReason | None:
        return None if self.last_command is None else self.last_command.reason
