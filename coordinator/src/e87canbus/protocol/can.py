"""CAN I/O boundaries and project-specific custom frame helpers."""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig

LOGGER = logging.getLogger(__name__)

BUTTON_RELEASED = 0x00
BUTTON_PRESSED = 0x01

LED_OFF = 0x00
LED_RED = 0x01
LED_GREEN = 0x02
LED_BLUE = 0x03
LED_AMBER = 0x04
LED_WHITE = 0x05

@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    is_extended_id: bool = False


@dataclass(frozen=True)
class RoutedCanFrame:
    """A transport frame paired with the network on which it was observed."""

    network: CanNetwork
    frame: CanFrame


class CanBus(Protocol):
    def send(self, frame: CanFrame) -> None:
        """Send one CAN frame."""

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        """Receive one CAN frame, or None on timeout."""


class RateLimitedCanBus:
    def __init__(
        self,
        bus: CanBus,
        policy: TxPolicyConfig,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bus = bus
        self._policy = policy
        self._clock = clock
        self._last_send_by_id: dict[int, tuple[CanFrame, float]] = {}
        self._send_times: deque[float] = deque()

    def send(self, frame: CanFrame) -> None:
        now = self._clock()
        last_send = self._last_send_by_id.get(frame.arbitration_id)
        if (
            last_send is not None
            and frame == last_send[0]
            and now - last_send[1] < self._policy.min_id_gap_s
        ):
            # Dropping avoids hiding a flood or delivering stale commands later.
            LOGGER.warning(
                "dropped rate-limited CAN frame: id=0x%03x reason=minimum-id-gap",
                frame.arbitration_id,
            )
            return

        cutoff = now - 1.0
        while self._send_times and self._send_times[0] < cutoff:
            self._send_times.popleft()
        if len(self._send_times) >= self._policy.max_frames_per_s:
            # Dropping avoids hiding a flood or delivering stale commands later.
            LOGGER.warning(
                "dropped rate-limited CAN frame: id=0x%03x reason=network-budget",
                frame.arbitration_id,
            )
            return

        self._bus.send(frame)
        self._last_send_by_id[frame.arbitration_id] = (frame, now)
        self._send_times.append(now)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        return self._bus.receive(timeout_s)


@dataclass(frozen=True)
class ArduinoButtonEventPayload:
    button_index: int
    pressed: bool


@dataclass(frozen=True)
class LedUpdatePayload:
    button_index: int
    colour_code: int


def encode_button_event(payload: ArduinoButtonEventPayload, ids: CustomCanIds) -> CanFrame:
    state = BUTTON_PRESSED if payload.pressed else BUTTON_RELEASED
    return CanFrame(ids.button_event, bytes([payload.button_index, state]))


def decode_button_event(frame: CanFrame, ids: CustomCanIds) -> ArduinoButtonEventPayload | None:
    if frame.arbitration_id != ids.button_event:
        return None
    if len(frame.data) != 2:
        raise ValueError("button event payload must be exactly 2 bytes")
    if frame.data[1] not in (BUTTON_RELEASED, BUTTON_PRESSED):
        raise ValueError("button event state must be released or pressed")
    return ArduinoButtonEventPayload(
        button_index=frame.data[0],
        pressed=frame.data[1] == BUTTON_PRESSED,
    )


def encode_led_update(payload: LedUpdatePayload, ids: CustomCanIds) -> CanFrame:
    return CanFrame(ids.led_update, bytes([payload.button_index, payload.colour_code]))


def decode_led_update(frame: CanFrame, ids: CustomCanIds) -> LedUpdatePayload | None:
    if frame.arbitration_id != ids.led_update:
        return None
    if len(frame.data) != 2:
        raise ValueError("LED update payload must be exactly 2 bytes")
    return LedUpdatePayload(button_index=frame.data[0], colour_code=frame.data[1])
