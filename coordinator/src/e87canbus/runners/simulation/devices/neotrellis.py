"""The simulated Arduino NeoTrellis button-pad node."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.config import CustomCanIds
from e87canbus.domain.devices.catalogue import DeviceRole
from e87canbus.domain.events import BUTTON_LED_COUNT
from e87canbus.domain.state import RGB_OFF
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    ButtonPadProgramPayload,
    CanFrame,
    decode_button_pad_commands,
    encode_button_event,
)
from e87canbus.protocol.generated import (
    BUTTON_PAD_EFFECT_BLINK,
    BUTTON_PAD_EFFECT_LENGTH,
)
from e87canbus.runners.simulation.devices.peer import SimulatedDeviceState, SimulatedRegistryPeer
from e87canbus.transport.isotp import IsoTpEndpoint

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulatedBlinkCommand:
    """One accepted ``0x701`` blink frame, decoded the way the firmware reads it."""

    button_index: int
    pulses: int
    rgb: tuple[int, int, int]
    sequence: int


class SimulatedNeoTrellisNode(SimulatedRegistryPeer):
    """Simulation of the current Arduino NeoTrellis CAN firmware."""

    def __init__(
        self,
        bus: CanEndpoint,
        ids: CustomCanIds,
        led_rgb: tuple[tuple[int, int, int], ...] = (RGB_OFF,) * BUTTON_LED_COUNT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            role=DeviceRole.BUTTON_PAD,
            bus=bus,
            ids=ids,
            clock=clock,
        )
        self.led_rgb = led_rgb
        self._pending_led_rgb: list[tuple[int, int, int]] | None = None
        self.button_pad_program: ButtonPadProgramPayload | None = None
        self.last_seen_monotonic_s: float | None = None
        self.effect_commands: list[SimulatedBlinkCommand] = []
        self.transport = IsoTpEndpoint(
            tx_id=ids.button_pad_transport_device_to_coordinator,
            rx_id=ids.button_pad_transport_coordinator_to_device,
            send_frame=bus.send,
            maximum_payload_length=ids.button_pad_transport_maximum_payload_length,
        )

    def send_button_event(self, button_index: int, pressed: bool) -> CanFrame | None:
        if not 0 <= button_index < BUTTON_LED_COUNT:
            raise ValueError(f"button_index must be between 0 and {BUTTON_LED_COUNT - 1}")
        if not self._operational_with_fresh_lease(self.clock()):
            return None
        frame = encode_button_event(
            ArduinoButtonEventPayload(
                button_index=button_index,
                pressed=pressed,
            ),
            self.ids,
        )
        self._require_bus().send(frame)
        return frame

    def process_pending_led_programs(self, *, limit: int = 64) -> list[ButtonPadProgramPayload]:
        programs: list[ButtonPadProgramPayload] = []
        self._process_pending(self.clock(), limit=limit, programs=programs)
        return programs

    def process_pending(self, now: float, *, limit: int = 64) -> int:
        return self._process_pending(now, limit=limit)

    def _process_pending(
        self,
        now: float,
        *,
        limit: int,
        programs: list[ButtonPadProgramPayload] | None = None,
    ) -> int:
        if limit < 1:
            raise ValueError("simulated device frame limit must be positive")
        bus = self._require_bus()
        processed = 0
        while processed < limit and (frame := bus.receive(timeout_s=0)) is not None:
            processed += 1
            if self._consume_registry_frame(frame, now):
                continue
            if frame.arbitration_id == self.ids.button_pad_effect:
                if (
                    self._operational_with_fresh_lease(now)
                    and len(frame.data) == BUTTON_PAD_EFFECT_LENGTH
                    and frame.data[0] == 1
                    and frame.data[1] == BUTTON_PAD_EFFECT_BLINK
                    and frame.data[2] < BUTTON_LED_COUNT
                    and frame.data[4] in (1, 2)
                ):
                    self.effect_commands.append(
                        SimulatedBlinkCommand(
                            frame.data[2],
                            frame.data[4],
                            (frame.data[5], frame.data[6], frame.data[7]),
                            frame.data[3],
                        )
                    )
                    self.last_seen_monotonic_s = now
                continue
            self.transport.on_frame(frame)
        self.transport.poll()
        while (payload := self.transport.receive_payload()) is not None:
            if not self._operational_with_fresh_lease(now):
                continue
            try:
                commands = decode_button_pad_commands(payload)
            except ValueError as exc:
                LOGGER.warning("sim neotrellis ignored malformed button-pad program: %s", exc)
                continue
            for program in commands:
                self.button_pad_program = program
                if program.replace_all:
                    self._pending_led_rgb = [program.track.rgb] * BUTTON_LED_COUNT
                if self._pending_led_rgb is None:
                    continue
                for index in range(BUTTON_LED_COUNT):
                    if program.target_mask & (1 << index):
                        self._pending_led_rgb[index] = program.track.rgb
                if program.commit:
                    self.led_rgb = tuple(self._pending_led_rgb)
                    self._pending_led_rgb = None
            self.last_seen_monotonic_s = now
            if programs is not None:
                programs.extend(commands)
        return processed

    def _operational_with_fresh_lease(self, now: float) -> bool:
        return (
            self.state is SimulatedDeviceState.OPERATIONAL
            and self._controller_lease_deadline is not None
            and now < self._controller_lease_deadline
        )
