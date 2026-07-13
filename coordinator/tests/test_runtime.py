import logging

import pytest
from e87canbus.application.controller import (
    ApplicationController,
    ApplicationEvent,
    ApplicationOutput,
)
from e87canbus.application.events import (
    ButtonLedCommand,
    LedColour,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import CoordinatorRuntime


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


class SpeedRouter(ProtocolRouter):
    def decode(self, routed: RoutedCanFrame) -> ApplicationEvent | None:
        return SpeedUpdateEvent(float(routed.frame.data[0]), routed.network)


class TickOutputApplication(ApplicationController):
    def tick(self, now: float) -> tuple[ApplicationOutput, ...]:
        del now
        return (ButtonLedCommand(button_index=0, colour=LedColour.BLUE),)


def test_protocol_router_scopes_button_decode_and_led_encode_to_kcan() -> None:
    ids = CustomCanIds()
    router = ProtocolRouter(ids)
    frame = CanFrame(ids.button_event, b"\x00\x01")

    assert router.decode(RoutedCanFrame(CanNetwork.PTCAN, frame)) is None
    event = router.decode(RoutedCanFrame(CanNetwork.KCAN, frame))
    assert event is not None

    output = ApplicationController().desired_outputs()[0]
    routed_output = router.encode(output)
    assert routed_output.network is CanNetwork.KCAN
    assert routed_output.frame.arbitration_id == ids.led_update


def test_runtime_processes_kcan_button_and_returns_led_on_kcan() -> None:
    ids = CustomCanIds()
    kcan = FakeBus([CanFrame(ids.button_event, b"\x00\x01")])
    ptcan = FakeBus()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: kcan, CanNetwork.PTCAN: ptcan},
        router=ProtocolRouter(ids),
        monotonic=lambda: 12.5,
    )

    assert runtime.drain_pending() == 1

    assert runtime.application.snapshot().steering_mode is SteeringMode.MANUAL
    assert kcan.sent == [CanFrame(ids.led_update, b"\x00\x04")]
    assert ptcan.sent == []
    health = runtime.application.state.can_health.latest_rx_monotonic_s
    assert health[CanNetwork.KCAN] == 12.5
    assert health[CanNetwork.PTCAN] is None


def test_unknown_and_malformed_frames_do_not_stop_runtime(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    bus = FakeBus(
        [
            CanFrame(0x123, b"\x00"),
            CanFrame(ids.button_event, b"\x00"),
            CanFrame(ids.button_event, b"\x00\x01"),
        ]
    )
    runtime = CoordinatorRuntime({CanNetwork.KCAN: bus}, router=ProtocolRouter(ids))

    with caplog.at_level(logging.WARNING):
        assert runtime.drain_pending() == 3

    assert runtime.application.snapshot().steering_mode is SteeringMode.MANUAL
    assert "ignored malformed recognized frame" in caplog.text


def test_unavailable_output_network_is_logged_and_does_not_crash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runtime = CoordinatorRuntime({CanNetwork.PTCAN: FakeBus()})

    with caplog.at_level(logging.WARNING):
        runtime.start()

    assert caplog.text.count("unavailable CAN network") == 2


def test_runtime_tick_sends_application_outputs() -> None:
    bus = FakeBus()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: bus},
        application=TickOutputApplication(),
        monotonic=lambda: 4.0,
    )

    runtime.tick()

    assert bus.sent == [CanFrame(CustomCanIds().led_update, b"\x00\x03")]


def test_speed_staleness_transitions_fresh_to_stale_and_fresh_again() -> None:
    clock = MutableClock()
    runtime = CoordinatorRuntime(
        {CanNetwork.FCAN: FakeBus()},
        router=SpeedRouter(),
        monotonic=clock,
    )
    speed_frame = RoutedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x2a"))

    runtime.process_frame(speed_frame)
    assert runtime.application.snapshot().speed_valid is True

    clock.now = 0.5
    runtime.tick()
    assert runtime.application.snapshot().speed_valid is True

    clock.now = 1.5
    runtime.tick()
    assert runtime.application.snapshot().speed_valid is False

    clock.now = 2.0
    runtime.process_frame(speed_frame)
    assert runtime.application.snapshot().speed_valid is True
