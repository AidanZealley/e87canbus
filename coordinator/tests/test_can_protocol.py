import logging

import pytest
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.protocol.can import (
    ArduinoButtonEventPayload,
    CanFrame,
    LedUpdatePayload,
    RateLimitedCanBus,
    RoutedCanFrame,
    decode_button_event,
    decode_led_update,
    encode_button_event,
    encode_led_update,
)


class FakeBus:
    def __init__(self, pending: list[CanFrame] | None = None) -> None:
        self.pending = pending or []
        self.sent: list[CanFrame] = []

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        return self.pending.pop(0) if self.pending else None


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_routed_envelope_preserves_network_without_mutating_frame() -> None:
    frame = CanFrame(0x123, b"\x01\x02")

    routed = RoutedCanFrame(CanNetwork.PTCAN, frame)

    assert routed.network is CanNetwork.PTCAN
    assert routed.frame is frame
    assert not hasattr(frame, "network")


def test_encode_and_decode_arduino_button_event() -> None:
    ids = CustomCanIds()
    frame = encode_button_event(ArduinoButtonEventPayload(button_index=4, pressed=True), ids)

    assert frame.arbitration_id == 0x700
    assert frame.data == bytes([4, 1])
    assert decode_button_event(frame, ids) == ArduinoButtonEventPayload(
        button_index=4,
        pressed=True,
    )


def test_decode_pi_led_update_payload() -> None:
    ids = CustomCanIds()
    frame = encode_led_update(LedUpdatePayload(button_index=2, colour_code=3), ids)

    assert frame.arbitration_id == 0x701
    assert decode_led_update(frame, ids) == LedUpdatePayload(button_index=2, colour_code=3)


def test_reject_invalid_payload_lengths() -> None:
    ids = CustomCanIds()

    with pytest.raises(ValueError, match="button event payload"):
        decode_button_event(CanFrame(ids.button_event, b"\x01"), ids)

    with pytest.raises(ValueError, match="LED update payload"):
        decode_led_update(CanFrame(ids.led_update, b"\x01"), ids)


def test_rate_limiter_drops_same_id_inside_gap_and_allows_it_after_gap(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock()
    underlying = FakeBus()
    bus = RateLimitedCanBus(underlying, TxPolicyConfig(), clock)
    frame = CanFrame(0x123, b"\x01")

    bus.send(frame)
    clock.now = 0.04
    with caplog.at_level(logging.WARNING):
        bus.send(frame)
    clock.now = 0.05
    bus.send(frame)

    assert underlying.sent == [frame, frame]
    assert "reason=minimum-id-gap" in caplog.text


def test_rate_limiter_allows_distinct_payloads_on_a_shared_id() -> None:
    clock = MutableClock()
    underlying = FakeBus()
    bus = RateLimitedCanBus(underlying, TxPolicyConfig(), clock)
    first = CanFrame(0x701, b"\x00\x03")
    second = CanFrame(0x701, b"\x03\x00")

    bus.send(first)
    bus.send(second)

    assert underlying.sent == [first, second]


def test_rate_limiter_tracks_id_gaps_independently_but_shares_network_budget(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock()
    underlying = FakeBus()
    policy = TxPolicyConfig(min_id_gap_s=0.5, max_frames_per_s=2)
    bus = RateLimitedCanBus(underlying, policy, clock)
    first = CanFrame(0x100, b"\x01")
    second = CanFrame(0x101, b"\x02")
    over_budget = CanFrame(0x102, b"\x03")

    bus.send(first)
    bus.send(second)
    with caplog.at_level(logging.WARNING):
        bus.send(over_budget)

    assert underlying.sent == [first, second]
    assert "reason=network-budget" in caplog.text


def test_rate_limiter_budget_refills_as_window_slides() -> None:
    clock = MutableClock()
    underlying = FakeBus()
    policy = TxPolicyConfig(min_id_gap_s=0.0, max_frames_per_s=2)
    bus = RateLimitedCanBus(underlying, policy, clock)
    frames = [CanFrame(0x100 + index, bytes([index])) for index in range(4)]

    bus.send(frames[0])
    clock.now = 0.2
    bus.send(frames[1])
    clock.now = 0.9
    bus.send(frames[2])
    clock.now = 1.1
    bus.send(frames[3])

    assert underlying.sent == [frames[0], frames[1], frames[3]]


def test_rate_limiter_receive_passes_through() -> None:
    frame = CanFrame(0x123, b"\x01")
    underlying = FakeBus([frame])
    bus = RateLimitedCanBus(underlying, TxPolicyConfig())

    received = bus.receive(timeout_s=0.25)

    assert received is frame
