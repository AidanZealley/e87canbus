import logging

import pytest
from e87canbus.application.events import (
    OFF_BUTTON_LEDS,
    ButtonLedState,
    LedColour,
    SetButtonLeds,
)
from e87canbus.cli.bench_pingpong import handle_frame, led_effect_for_button_event, run_pingpong
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.generated import BUTTON_PRESSED, BUTTON_RELEASED
from e87canbus.protocol.router import ProtocolRouter


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


def executor_for(bus: FakeBus, ids: CustomCanIds) -> EffectExecutor:
    router = ProtocolRouter(ids)
    return EffectExecutor(
        {CanNetwork.KCAN: SafeCanTransmitter(bus, TxPolicyConfig())},
        router,
    )


def test_pressed_button_frame_produces_green_led_effect() -> None:
    ids = CustomCanIds()

    effect = led_effect_for_button_event(
        CanFrame(0x700, bytes([0, BUTTON_PRESSED])),
        ids,
        OFF_BUTTON_LEDS,
    )

    assert effect == SetButtonLeds(
        ButtonLedState((LedColour.GREEN,) + (LedColour.OFF,) * 15)
    )


def test_released_button_frame_produces_off_led_effect() -> None:
    ids = CustomCanIds()

    effect = led_effect_for_button_event(
        CanFrame(0x700, bytes([0, BUTTON_RELEASED])),
        ids,
        ButtonLedState((LedColour.GREEN,) + (LedColour.OFF,) * 15),
    )

    assert effect == SetButtonLeds(OFF_BUTTON_LEDS)


def test_unknown_ids_are_ignored() -> None:
    ids = CustomCanIds()
    bus = FakeBus([])

    state = handle_frame(
        executor_for(bus, ids), CanFrame(0x123, b"\x00\x01"), ids, OFF_BUTTON_LEDS
    )

    assert bus.sent == []
    assert state == OFF_BUTTON_LEDS


def test_malformed_payload_logs_warning_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    bus = FakeBus([])

    with caplog.at_level(logging.WARNING):
        state = handle_frame(
            executor_for(bus, ids), CanFrame(0x700, b"\x00"), ids, OFF_BUTTON_LEDS
        )

    assert bus.sent == []
    assert state == OFF_BUTTON_LEDS
    assert "malformed button event frame" in caplog.text


def test_receive_timeout_does_not_crash() -> None:
    ids = CustomCanIds()
    bus = FakeBus([None])

    with pytest.raises(KeyboardInterrupt):
        run_pingpong(bus, executor_for(bus, ids), ids, receive_timeout_s=0.01)

    assert bus.sent == []
