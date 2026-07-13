import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import replace

import e87canbus.live as live
import pytest
from e87canbus.config import CanNetwork, CustomCanIds, default_config, simulator_config
from e87canbus.live import InboxOverflow, read_frames_into_queue, run_coordinator_loop
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import CoordinatorRuntime, ReceivedCanFrame


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


class RecordingStop(threading.Event):
    def __init__(self, stop_after_waits: int) -> None:
        super().__init__()
        self.stop_after_waits = stop_after_waits
        self.waits: list[float | None] = []

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        if len(self.waits) >= self.stop_after_waits:
            self.set()
        return self.is_set()


class FakeSocketCanBus:
    instances: list["FakeSocketCanBus"] = []

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self.sent: list[CanFrame] = []
        self.instances.append(self)

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        return None

    def shutdown(self) -> None:
        pass


class OverflowingSocketCanBus(FakeSocketCanBus):
    def __init__(self, interface: str) -> None:
        super().__init__(interface)
        self.shutdown_called = False
        self._frames_remaining = 2 if interface == "can0" else 0

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        if self._frames_remaining == 0:
            return None
        self._frames_remaining -= 1
        return CanFrame(0x123, b"\x01")

    def shutdown(self) -> None:
        self.shutdown_called = True


class ImmediateThread:
    def __init__(
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
        daemon: bool,
        name: str,
    ) -> None:
        del daemon, name
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)

    def join(self, timeout: float | None = None) -> None:
        del timeout


def start_runtime_then_stop(
    runtime: CoordinatorRuntime,
    frames: queue.Queue[ReceivedCanFrame],
    stop: threading.Event,
    tick_interval_s: float,
    queue_latency_warning_s: float,
) -> None:
    del frames, tick_interval_s, queue_latency_warning_s
    runtime.start()
    stop.set()


class AdvancingQueue(queue.Queue[ReceivedCanFrame]):
    def __init__(self, clock: MutableClock, jump_s: float | None = None) -> None:
        super().__init__()
        self.clock = clock
        self.jump_s = jump_s

    def get(self, block: bool = True, timeout: float | None = None) -> ReceivedCanFrame:
        try:
            return super().get(block=False)
        except queue.Empty:
            if self.jump_s is not None:
                self.clock.now += self.jump_s
                self.jump_s = None
            else:
                self.clock.now += timeout or 0.0
            raise


class TickRecordingRuntime(CoordinatorRuntime):
    def __init__(
        self,
        stop: threading.Event,
        stop_after: int,
        clock: Callable[[], float],
        receivers: dict[CanNetwork, BlockingFakeBus] | None = None,
    ) -> None:
        super().__init__(receivers or {}, monotonic=clock)
        self.clock = clock
        self.stop = stop
        self.stop_after = stop_after
        self.tick_times: list[float] = []

    def tick(self) -> None:
        self.tick_times.append(self.clock())
        if len(self.tick_times) >= self.stop_after:
            self.stop.set()
        super().tick()


def test_reader_timestamps_frame_at_receive_and_stops() -> None:
    bus = BlockingFakeBus()
    frames: queue.Queue[ReceivedCanFrame] = queue.Queue()
    stop = threading.Event()
    overflow = InboxOverflow()
    clock = MutableClock(12.5)
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.PTCAN, bus, frames, stop, overflow, clock, 0.01),
    )

    reader.start()
    bus.received.put(frame)
    received = frames.get(timeout=0.2)
    stop.set()
    reader.join(timeout=0.2)

    assert received == ReceivedCanFrame(CanNetwork.PTCAN, frame, 12.5)
    assert not overflow.occurred
    assert not reader.is_alive()


def test_reader_logs_receive_errors_and_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = BlockingFakeBus()
    frames: queue.Queue[ReceivedCanFrame] = queue.Queue()
    stop = threading.Event()
    overflow = InboxOverflow()
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.FCAN, bus, frames, stop, overflow, time.monotonic, 0.01),
    )

    with caplog.at_level(logging.WARNING):
        reader.start()
        bus.received.put(OSError("receive failed"))
        bus.received.put(frame)
        received = frames.get(timeout=0.2)
        stop.set()
        reader.join(timeout=0.2)

    assert received.network is CanNetwork.FCAN
    assert received.frame == frame
    assert "failed to receive CAN frame and continued" in caplog.text
    assert not reader.is_alive()


def test_reader_receive_error_backoff_is_capped() -> None:
    bus = BlockingFakeBus()
    frames: queue.Queue[ReceivedCanFrame] = queue.Queue()
    stop = RecordingStop(stop_after_waits=6)
    for _ in range(6):
        bus.received.put(OSError("receive failed"))

    read_frames_into_queue(CanNetwork.FCAN, bus, frames, stop, InboxOverflow())

    assert stop.waits == pytest.approx([0.05, 0.1, 0.2, 0.4, 0.8, 1.0])
    assert frames.empty()


def test_coordinator_loop_processes_queued_frames_and_ticks_on_cadence() -> None:
    clock = MutableClock()
    frames = AdvancingQueue(clock)
    stop = threading.Event()
    bus = BlockingFakeBus()
    runtime = TickRecordingRuntime(
        stop,
        stop_after=3,
        clock=clock,
        receivers={CanNetwork.KCAN: bus},
    )
    frames.put(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            0.0,
        )
    )

    run_coordinator_loop(
        runtime,
        frames,
        stop,
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
        clock=clock,
    )

    assert runtime.snapshot().steering_mode.value == "manual"
    assert runtime.tick_times == pytest.approx([0.1, 0.2, 0.3])


def test_coordinator_loop_resynchronizes_after_large_clock_jump() -> None:
    clock = MutableClock()
    frames = AdvancingQueue(clock, jump_s=1.0)
    stop = threading.Event()
    runtime = TickRecordingRuntime(stop, stop_after=2, clock=clock)

    run_coordinator_loop(
        runtime,
        frames,
        stop,
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
        clock=clock,
    )

    assert runtime.tick_times == pytest.approx([1.0, 1.1])


def test_coordinator_loop_warns_about_latency_without_rewriting_receive_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock(2.0)
    frames = AdvancingQueue(clock)
    stop = threading.Event()
    runtime = TickRecordingRuntime(stop, stop_after=1, clock=clock)
    frames.put(ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x01"), 0.5))

    with caplog.at_level(logging.WARNING):
        run_coordinator_loop(
            runtime,
            frames,
            stop,
            tick_interval_s=0.1,
            queue_latency_warning_s=1.0,
            clock=clock,
        )

    health = runtime.health.latest_rx_monotonic_s
    assert health[CanNetwork.FCAN] == 0.5
    assert "network=fcan latency_s=1.500" in caplog.text


def test_live_threads_route_button_event_to_kcan_led_reply() -> None:
    ids = CustomCanIds()
    bus = BlockingFakeBus()
    frames: queue.Queue[ReceivedCanFrame] = queue.Queue()
    stop = threading.Event()
    overflow = InboxOverflow()
    router = ProtocolRouter()
    runtime = CoordinatorRuntime(
        {CanNetwork.KCAN: bus},
        router=router,
        executor=EffectExecutor(
            {
                CanNetwork.KCAN: SafeCanTransmitter(
                    bus,
                    default_config().tx_policy,
                )
            },
            router,
        ),
    )
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.KCAN, bus, frames, stop, overflow, time.monotonic, 0.01),
    )
    coordinator = threading.Thread(
        target=run_coordinator_loop,
        args=(runtime, frames, stop, 0.1, 1.0),
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


def test_default_live_composition_emits_no_startup_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSocketCanBus.instances = []
    monkeypatch.setattr(live, "SocketCanBus", FakeSocketCanBus)
    monkeypatch.setattr(live, "run_coordinator_loop", start_runtime_then_stop)

    assert live.run_live(default_config()) == 0

    assert all(not bus.sent for bus in FakeSocketCanBus.instances)


def test_explicit_kcan_tx_composition_emits_rate_limited_startup_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSocketCanBus.instances = []
    monkeypatch.setattr(live, "SocketCanBus", FakeSocketCanBus)
    monkeypatch.setattr(live, "run_coordinator_loop", start_runtime_then_stop)

    assert live.run_live(simulator_config()) == 0

    kcan = next(bus for bus in FakeSocketCanBus.instances if bus.interface == "can0")
    assert kcan.sent == [CanFrame(0x701, b"\x00\x03"), CanFrame(0x701, b"\x03\x00")]


def test_live_inbox_overflow_stops_once_cleans_up_and_returns_nonzero(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSocketCanBus.instances = []
    monkeypatch.setattr(live, "SocketCanBus", OverflowingSocketCanBus)
    monkeypatch.setattr(live.threading, "Thread", ImmediateThread)
    config = replace(default_config(), runtime_inbox_capacity=1)

    with caplog.at_level(logging.ERROR):
        result = live.run_live(config)

    assert result == 1
    assert caplog.text.count("live CAN inbox overflow") == 1
    assert "network=kcan capacity=1" in caplog.text
    assert all(
        isinstance(bus, OverflowingSocketCanBus) and bus.shutdown_called
        for bus in FakeSocketCanBus.instances
    )
