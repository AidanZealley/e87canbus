import logging

import pytest
from e87canbus.application.events import ApplicationEvent, ButtonPressed, SpeedObserved
from e87canbus.application.state import SpeedSample, SteeringMode
from e87canbus.config import CanNetwork, CustomCanIds, TxPolicyConfig
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import CoordinatorRuntime, ReceivedCanFrame


class FakeEndpoint:
    def __init__(self, pending: list[CanFrame] | None = None) -> None:
        self.pending = pending or []
        self.sent: list[CanFrame] = []

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        return self.pending.pop(0) if self.pending else None


class ReceiveOnly:
    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        return None


class FailingTransmitter:
    def send(self, frame: CanFrame) -> None:
        raise OSError(f"failed {frame.arbitration_id}")


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class SpeedRouter(ProtocolRouter):
    def decode(
        self,
        routed: RoutedCanFrame,
        observed_at: float,
    ) -> ApplicationEvent | None:
        return SpeedObserved(
            SpeedSample(float(routed.frame.data[0]), observed_at, routed.network)
        )


def runtime_with_kcan(endpoint: FakeEndpoint) -> CoordinatorRuntime:
    router = ProtocolRouter()
    return CoordinatorRuntime(
        {CanNetwork.KCAN: endpoint},
        router=router,
        executor=EffectExecutor(
            {
                CanNetwork.KCAN: SafeCanTransmitter(
                    endpoint,
                    TxPolicyConfig(),
                    lambda: 0.0,
                )
            },
            router,
        ),
        monotonic=lambda: 12.5,
    )


def test_protocol_router_discards_releases_and_scopes_button_decode_to_kcan() -> None:
    ids = CustomCanIds()
    router = ProtocolRouter(ids)
    pressed = CanFrame(ids.button_event, b"\x00\x01")
    released = CanFrame(ids.button_event, b"\x00\x00")

    assert router.decode(RoutedCanFrame(CanNetwork.PTCAN, pressed), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, released), 1.0) is None
    assert router.decode(RoutedCanFrame(CanNetwork.KCAN, pressed), 1.0) == ButtonPressed(0)


def test_runtime_processes_kcan_button_and_returns_led_on_kcan() -> None:
    ids = CustomCanIds()
    kcan = FakeEndpoint([CanFrame(ids.button_event, b"\x00\x01")])
    runtime = runtime_with_kcan(kcan)

    assert runtime.drain_pending() == 1

    assert runtime.snapshot().steering_mode is SteeringMode.MANUAL
    assert kcan.sent == [CanFrame(ids.led_update, b"\x00\x04")]
    assert runtime.health.latest_rx_monotonic_s[CanNetwork.KCAN] == 12.5


def test_unknown_and_malformed_frames_do_not_stop_runtime(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ids = CustomCanIds()
    bus = FakeEndpoint(
        [
            CanFrame(0x123, b"\x00"),
            CanFrame(ids.button_event, b"\x00"),
            CanFrame(ids.button_event, b"\x00\x01"),
        ]
    )
    runtime = runtime_with_kcan(bus)

    with caplog.at_level(logging.WARNING):
        assert runtime.drain_pending() == 3

    assert runtime.snapshot().steering_mode is SteeringMode.MANUAL
    assert "ignored malformed recognized frame" in caplog.text


def test_default_runtime_has_no_transmit_capability(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = FakeEndpoint()
    runtime = CoordinatorRuntime({CanNetwork.KCAN: bus})

    with caplog.at_level(logging.WARNING):
        runtime.start()

    assert bus.sent == []
    assert caplog.text.count("unavailable TX capability") == 2


def test_effect_failure_does_not_roll_back_committed_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    router = ProtocolRouter()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: ReceiveOnly()},
        router=router,
        executor=EffectExecutor(
            {
                CanNetwork.KCAN: SafeCanTransmitter(
                    FailingTransmitter(),
                    TxPolicyConfig(),
                )
            },
            router,
        ),
    )

    with caplog.at_level(logging.WARNING):
        runtime.process_frame(
            ReceivedCanFrame(
                CanNetwork.KCAN,
                CanFrame(CustomCanIds().button_event, b"\x00\x01"),
                1.0,
            )
        )

    assert runtime.snapshot().steering_mode is SteeringMode.MANUAL
    assert "failed to execute effect and continued" in caplog.text


def test_receive_only_runtime_capability_has_no_send_method() -> None:
    receiver = ReceiveOnly()

    runtime = CoordinatorRuntime({CanNetwork.KCAN: receiver})

    assert runtime.receivers[CanNetwork.KCAN] is receiver
    assert not hasattr(receiver, "send")


def test_speed_staleness_transitions_fresh_to_stale_and_fresh_again() -> None:
    clock = MutableClock()
    runtime = CoordinatorRuntime(
        {CanNetwork.FCAN: FakeEndpoint()},
        router=SpeedRouter(),
        monotonic=clock,
    )
    speed_frame = CanFrame(0x123, b"\x2a")

    runtime.process_frame(ReceivedCanFrame(CanNetwork.FCAN, speed_frame, 0.0))
    assert runtime.snapshot().speed_valid is True

    clock.now = 0.5
    runtime.tick()
    assert runtime.snapshot().speed_valid is True

    clock.now = 1.5
    runtime.tick()
    assert runtime.snapshot().speed_valid is False

    runtime.process_frame(ReceivedCanFrame(CanNetwork.FCAN, speed_frame, 2.0))
    assert runtime.snapshot().speed_valid is True


def test_old_queued_speed_frame_keeps_ingress_time_when_processed_later() -> None:
    clock = MutableClock(5.0)
    runtime = CoordinatorRuntime(
        {CanNetwork.FCAN: FakeEndpoint()},
        router=SpeedRouter(),
        monotonic=clock,
    )

    runtime.process_frame(
        ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x2a"), received_at=1.0)
    )
    runtime.tick()

    assert runtime.health.latest_rx_monotonic_s[CanNetwork.FCAN] == 1.0
    assert runtime.state.speed_sample == SpeedSample(42.0, 1.0, CanNetwork.FCAN)
    assert runtime.snapshot().speed_valid is False
