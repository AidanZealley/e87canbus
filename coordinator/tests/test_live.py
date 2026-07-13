import logging
import queue
import threading

import pytest
from e87canbus.application.controller import ApplicationController, ApplicationOutput
from e87canbus.config import CanNetwork, CustomCanIds
from e87canbus.live import read_frames_into_queue, run_coordinator_loop
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.runtime import CoordinatorRuntime


class BlockingFakeBus:
    def __init__(self) -> None:
        self.received: queue.Queue[CanFrame | OSError] = queue.Queue()
        self.sent: queue.Queue[CanFrame] = queue.Queue()

    def send(self, frame: CanFrame) -> None:
        self.sent.put(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        try:
            received = self.received.get(timeout=timeout_s)
        except queue.Empty:
            return None
        if isinstance(received, OSError):
            raise received
        return received


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class AdvancingQueue(queue.Queue[RoutedCanFrame]):
    def __init__(self, clock: MutableClock, jump_s: float | None = None) -> None:
        super().__init__()
        self.clock = clock
        self.jump_s = jump_s

    def get(self, block: bool = True, timeout: float | None = None) -> RoutedCanFrame:
        try:
            return super().get(block=False)
        except queue.Empty:
            if self.jump_s is not None:
                self.clock.now += self.jump_s
                self.jump_s = None
            else:
                self.clock.now += timeout or 0.0
            raise


class TickRecordingApplication(ApplicationController):
    def __init__(self, stop: threading.Event, stop_after: int) -> None:
        super().__init__()
        self.stop = stop
        self.stop_after = stop_after
        self.tick_times: list[float] = []

    def tick(self, now: float) -> tuple[ApplicationOutput, ...]:
        self.tick_times.append(now)
        if len(self.tick_times) >= self.stop_after:
            self.stop.set()
        return ()


def test_reader_enqueues_frames_with_the_source_network_and_stops() -> None:
    bus = BlockingFakeBus()
    frames: queue.Queue[RoutedCanFrame] = queue.Queue()
    stop = threading.Event()
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.PTCAN, bus, frames, stop, 0.01),
    )

    reader.start()
    bus.received.put(frame)
    routed = frames.get(timeout=0.2)
    stop.set()
    reader.join(timeout=0.2)

    assert routed == RoutedCanFrame(CanNetwork.PTCAN, frame)
    assert not reader.is_alive()


def test_reader_logs_receive_errors_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = BlockingFakeBus()
    frames: queue.Queue[RoutedCanFrame] = queue.Queue()
    stop = threading.Event()
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.FCAN, bus, frames, stop, 0.01),
    )

    with caplog.at_level(logging.WARNING):
        reader.start()
        bus.received.put(OSError("receive failed"))
        bus.received.put(frame)
        routed = frames.get(timeout=0.2)
        stop.set()
        reader.join(timeout=0.2)

    assert routed == RoutedCanFrame(CanNetwork.FCAN, frame)
    assert "failed to receive CAN frame and continued" in caplog.text
    assert not reader.is_alive()


def test_coordinator_loop_processes_queued_frames_and_ticks_on_cadence() -> None:
    clock = MutableClock()
    frames = AdvancingQueue(clock)
    stop = threading.Event()
    application = TickRecordingApplication(stop, stop_after=3)
    bus = BlockingFakeBus()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: bus},
        application=application,
        monotonic=clock,
        tx_networks=frozenset({CanNetwork.KCAN}),
    )
    frames.put(
        RoutedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
        )
    )

    run_coordinator_loop(runtime, frames, stop, tick_interval_s=0.1, clock=clock)

    assert runtime.application.snapshot().steering_mode.value == "manual"
    assert application.tick_times == pytest.approx([0.1, 0.2, 0.3])


def test_coordinator_loop_resynchronizes_after_large_clock_jump() -> None:
    clock = MutableClock()
    frames = AdvancingQueue(clock, jump_s=1.0)
    stop = threading.Event()
    application = TickRecordingApplication(stop, stop_after=2)
    runtime = CoordinatorRuntime({}, application=application, monotonic=clock)

    run_coordinator_loop(runtime, frames, stop, tick_interval_s=0.1, clock=clock)

    assert application.tick_times == pytest.approx([1.0, 1.1])


def test_live_threads_route_button_event_to_kcan_led_reply() -> None:
    ids = CustomCanIds()
    bus = BlockingFakeBus()
    frames: queue.Queue[RoutedCanFrame] = queue.Queue()
    stop = threading.Event()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: bus},
        tx_networks=frozenset({CanNetwork.KCAN}),
    )
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.KCAN, bus, frames, stop, 0.01),
    )
    coordinator = threading.Thread(
        target=run_coordinator_loop,
        args=(runtime, frames, stop, 0.1),
    )

    reader.start()
    coordinator.start()
    bus.sent.get(timeout=0.2)
    bus.sent.get(timeout=0.2)
    bus.received.put(CanFrame(ids.button_event, b"\x00\x01"))
    reply = bus.sent.get(timeout=0.2)
    stop.set()
    reader.join(timeout=0.2)
    coordinator.join(timeout=0.2)

    assert reply == CanFrame(ids.led_update, b"\x00\x04")
    assert not reader.is_alive()
    assert not coordinator.is_alive()
