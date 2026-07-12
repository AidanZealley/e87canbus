import logging

import pytest
from e87canbus.cli.bench_pingpong import handle_frame, led_update_for_button_event, run_pingpong
from e87canbus.config import CustomCanIds
from e87canbus.protocol.can import BUTTON_PRESSED, BUTTON_RELEASED, LED_GREEN, LED_OFF, CanFrame


class FakeBus:
    def __init__(self, received: list[CanFrame | None]) -> None:
        self.received = received
        self.sent: list[CanFrame] = []

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        if not self.received:
            raise KeyboardInterrupt
        return self.received.pop(0)


def test_pressed_button_frame_produces_green_led_frame() -> None:
    ids = CustomCanIds()
    reply = led_update_for_button_event(CanFrame(0x700, bytes([0, BUTTON_PRESSED])), ids)

    assert reply == CanFrame(0x701, bytes([0, LED_GREEN]))


def test_released_button_frame_produces_off_led_frame() -> None:
    ids = CustomCanIds()
    reply = led_update_for_button_event(CanFrame(0x700, bytes([0, BUTTON_RELEASED])), ids)

    assert reply == CanFrame(0x701, bytes([0, LED_OFF]))


def test_unknown_ids_are_ignored() -> None:
    bus = FakeBus([])

    handle_frame(bus, CanFrame(0x123, b"\x00\x01"), CustomCanIds())

    assert bus.sent == []


def test_malformed_payload_logs_warning_and_continues(caplog: pytest.LogCaptureFixture) -> None:
    bus = FakeBus([])

    with caplog.at_level(logging.WARNING):
        handle_frame(bus, CanFrame(0x700, b"\x00"), CustomCanIds())

    assert bus.sent == []
    assert "malformed button event frame" in caplog.text


def test_receive_timeout_does_not_crash() -> None:
    bus = FakeBus([None])

    with pytest.raises(KeyboardInterrupt):
        run_pingpong(bus, CustomCanIds(), receive_timeout_s=0.01)

    assert bus.sent == []
