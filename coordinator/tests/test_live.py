import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import replace

import e87canbus.live as live
import pytest
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.config import CanNetwork, CustomCanIds, default_config, simulator_config
from e87canbus.live import InboxOverflow, read_frames_into_queue, run_coordinator_loop
from e87canbus.output import EffectExecutor, SafeCanTransmitter
from e87canbus.protocol.can import CanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.runtime import (
    CanEffectExecutionFailed,
    CanReaderFailed,
    CoordinatorKernel,
    KernelInput,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)


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


class FailingTransmitter:
    def send(self, frame: CanFrame) -> None:
        raise OSError(f"failed {frame.arbitration_id}")


class RecordingActuator:
    def __init__(self) -> None:
        self.commands: list[SetSteeringAssistance] = []

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.commands.append(command)


class FailingFallbackActuator(RecordingActuator):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def set_assistance(self, command: SetSteeringAssistance) -> None:
        self.attempts += 1
        if self.attempts >= 2:
            raise OSError(f"failed attempt {self.attempts}")
        super().set_assistance(command)


class MutableClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


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


class AdvancingQueue(queue.Queue[KernelInput]):
    def __init__(self, clock: MutableClock, jump_s: float | None = None) -> None:
        super().__init__()
        self.clock = clock
        self.jump_s = jump_s

    def get(self, block: bool = True, timeout: float | None = None) -> KernelInput:
        try:
            return super().get(block=False)
        except queue.Empty:
            if self.jump_s is not None:
                self.clock.now += self.jump_s
                self.jump_s = None
            else:
                self.clock.now += timeout or 0.0
            raise


class RecordingKernel(CoordinatorKernel):
    def __init__(
        self,
        stop: threading.Event | None = None,
        stop_after_ticks: int | None = None,
        after_frame: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.stop = stop
        self.stop_after_ticks = stop_after_ticks
        self.after_frame = after_frame
        self.inputs: list[KernelInput] = []
        self.dispatch_thread_ids: list[int] = []
        self.tick_times: list[float] = []

    def dispatch(self, kernel_input: KernelInput):
        self.inputs.append(kernel_input)
        self.dispatch_thread_ids.append(threading.get_ident())
        result = super().dispatch(kernel_input)
        if isinstance(kernel_input, ReceivedCanFrame) and self.after_frame is not None:
            self.after_frame()
        if isinstance(kernel_input, TimerElapsed):
            self.tick_times.append(kernel_input.now)
            if (
                self.stop is not None
                and self.stop_after_ticks is not None
                and len(self.tick_times) >= self.stop_after_ticks
            ):
                self.stop.set()
        return result


def start_kernel_then_stop(
    kernel: CoordinatorKernel,
    executor: EffectExecutor,
    inbox: queue.Queue[KernelInput],
    stop: threading.Event,
    overflow: InboxOverflow,
    tick_interval_s: float,
    queue_latency_warning_s: float,
) -> bool:
    del inbox, overflow, tick_interval_s, queue_latency_warning_s
    commit = kernel.dispatch(KernelStarted(0.0))
    assert commit is not None
    executor.execute(commit.effects)
    stop.set()
    kernel.dispatch(ShutdownRequested(0.0))
    return False


def test_reader_timestamps_frame_at_receive_and_stops() -> None:
    bus = BlockingFakeBus()
    inbox: queue.Queue[KernelInput] = queue.Queue()
    stop = threading.Event()
    overflow = InboxOverflow()
    clock = MutableClock(12.5)
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.PTCAN, bus, inbox, stop, overflow, clock, 0.01),
    )

    reader.start()
    bus.received.put(frame)
    received = inbox.get(timeout=0.2)
    stop.set()
    reader.join(timeout=0.2)

    assert received == ReceivedCanFrame(CanNetwork.PTCAN, frame, 12.5)
    assert overflow.kernel_input is None
    assert not reader.is_alive()


def test_reader_recovers_after_one_receive_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bus = BlockingFakeBus()
    inbox: queue.Queue[KernelInput] = queue.Queue()
    stop = threading.Event()
    frame = CanFrame(0x123, b"\x01")
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.FCAN, bus, inbox, stop, InboxOverflow(), time.monotonic, 0.01),
    )

    with caplog.at_level(logging.WARNING):
        reader.start()
        bus.received.put(OSError("receive failed"))
        bus.received.put(frame)
        received = inbox.get(timeout=0.3)
        stop.set()
        reader.join(timeout=0.2)

    assert isinstance(received, ReceivedCanFrame)
    assert received.frame == frame
    assert "failed to receive CAN frame and continued" in caplog.text
    assert not reader.is_alive()


def test_repeated_reader_errors_become_one_kernel_input_and_reader_exits() -> None:
    bus = BlockingFakeBus()
    inbox: queue.Queue[KernelInput] = queue.Queue()
    stop = threading.Event()
    for _ in range(live.MAX_CONSECUTIVE_READER_ERRORS):
        bus.received.put(OSError("receive failed"))

    read_frames_into_queue(CanNetwork.FCAN, bus, inbox, stop, InboxOverflow())

    failure = inbox.get_nowait()
    assert isinstance(failure, CanReaderFailed)
    assert failure.network is CanNetwork.FCAN
    assert failure.message == "receive failed"
    assert inbox.empty()


def test_coordinator_loop_processes_frames_and_ticks_on_cadence() -> None:
    clock = MutableClock()
    inbox = AdvancingQueue(clock)
    stop = threading.Event()
    kernel = RecordingKernel(stop, stop_after_ticks=3)
    inbox.put(
        ReceivedCanFrame(
            CanNetwork.KCAN,
            CanFrame(CustomCanIds().button_event, b"\x00\x01"),
            0.0,
        )
    )

    failed = run_coordinator_loop(
        kernel,
        EffectExecutor(),
        inbox,
        stop,
        InboxOverflow(),
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
        clock=clock,
    )

    assert failed is False
    assert kernel.snapshot().steering_mode.value == "manual"
    assert kernel.tick_times == pytest.approx([0.1, 0.2, 0.3])


def test_coordinator_loop_resynchronizes_after_large_clock_jump() -> None:
    clock = MutableClock()
    inbox = AdvancingQueue(clock, jump_s=1.0)
    stop = threading.Event()
    kernel = RecordingKernel(stop, stop_after_ticks=2)

    run_coordinator_loop(
        kernel,
        EffectExecutor(),
        inbox,
        stop,
        InboxOverflow(),
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
        clock=clock,
    )

    assert kernel.tick_times == pytest.approx([1.0, 1.1])


def test_sustained_unknown_traffic_cannot_starve_timer_dispatch() -> None:
    clock = MutableClock()
    inbox = AdvancingQueue(clock)
    stop = threading.Event()
    kernel = RecordingKernel(
        stop,
        stop_after_ticks=1,
        after_frame=lambda: setattr(clock, "now", clock.now + 0.01),
    )
    for _ in range(100):
        inbox.put(ReceivedCanFrame(CanNetwork.KCAN, CanFrame(0x123, b""), clock()))

    run_coordinator_loop(
        kernel,
        EffectExecutor(),
        inbox,
        stop,
        InboxOverflow(),
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
        clock=clock,
    )

    assert len(kernel.tick_times) == 1
    assert kernel.tick_times[0] <= 0.11
    assert not inbox.empty()


def test_queue_latency_warning_does_not_rewrite_receive_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock(2.0)
    inbox = AdvancingQueue(clock)
    stop = threading.Event()
    kernel = RecordingKernel(stop, stop_after_ticks=1)
    inbox.put(ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x01"), 0.5))

    with caplog.at_level(logging.WARNING):
        run_coordinator_loop(
            kernel,
            EffectExecutor(),
            inbox,
            stop,
            InboxOverflow(),
            tick_interval_s=0.1,
            queue_latency_warning_s=1.0,
            clock=clock,
        )

    assert "network=fcan latency_s=1.500" in caplog.text


def test_effect_failure_is_dispatched_after_execution_without_reentry() -> None:
    stop = threading.Event()
    kernel = RecordingKernel(stop)
    router = ProtocolRouter()
    executor = EffectExecutor(
        {
            CanNetwork.KCAN: SafeCanTransmitter(
                FailingTransmitter(),
                default_config().tx_policy,
            )
        },
        router,
    )

    failed = run_coordinator_loop(
        kernel,
        executor,
        queue.Queue(),
        stop,
        InboxOverflow(),
        tick_interval_s=0.1,
        queue_latency_warning_s=1.0,
    )

    assert failed is True
    assert isinstance(kernel.inputs[0], KernelStarted)
    assert isinstance(kernel.inputs[1], CanEffectExecutionFailed)
    assert isinstance(kernel.inputs[2], CanEffectExecutionFailed)
    assert isinstance(kernel.inputs[3], ShutdownRequested)
    assert len(set(kernel.dispatch_thread_ids)) == 1


def test_live_threads_use_one_dispatch_thread_and_stop_boundedly() -> None:
    ids = CustomCanIds()
    bus = BlockingFakeBus()
    inbox: queue.Queue[KernelInput] = queue.Queue()
    stop = threading.Event()
    overflow = InboxOverflow()
    router = ProtocolRouter()
    kernel = RecordingKernel(stop)
    executor = EffectExecutor(
        {
            CanNetwork.KCAN: SafeCanTransmitter(
                bus,
                default_config().tx_policy,
            )
        },
        router,
    )
    reader = threading.Thread(
        target=read_frames_into_queue,
        args=(CanNetwork.KCAN, bus, inbox, stop, overflow, time.monotonic, 0.01),
    )
    result: list[bool] = []
    coordinator = threading.Thread(
        target=lambda: result.append(
            run_coordinator_loop(kernel, executor, inbox, stop, overflow, 0.1, 1.0)
        )
    )

    reader.start()
    coordinator.start()
    bus.sent.get(timeout=0.2)
    bus.sent.get(timeout=0.2)
    bus.received.put(CanFrame(ids.button_event, b"\x00\x01"))
    reply = bus.sent.get(timeout=0.2)
    stop.set()
    reader.join(timeout=0.3)
    coordinator.join(timeout=0.3)

    assert reply == CanFrame(ids.led_update, b"\x00\x04")
    assert result == [False]
    assert len(set(kernel.dispatch_thread_ids)) == 1
    assert not reader.is_alive()
    assert not coordinator.is_alive()


def test_reader_fault_causes_clean_nonzero_loop_shutdown() -> None:
    inbox: queue.Queue[KernelInput] = queue.Queue()
    inbox.put(CanReaderFailed(CanNetwork.FCAN, 1.0, "receive failed"))
    kernel = RecordingKernel()

    failed = run_coordinator_loop(
        kernel,
        EffectExecutor(),
        inbox,
        threading.Event(),
        InboxOverflow(),
        0.1,
        1.0,
    )

    assert failed is True
    assert kernel.health.for_network(CanNetwork.FCAN).fault is not None
    assert isinstance(kernel.inputs[-1], ShutdownRequested)


def test_reader_fault_commands_fallback_before_shutdown() -> None:
    inbox: queue.Queue[KernelInput] = queue.Queue()
    inbox.put(CanReaderFailed(CanNetwork.FCAN, 1.0, "receive failed"))
    actuator = RecordingActuator()

    failed = run_coordinator_loop(
        CoordinatorKernel(),
        EffectExecutor(steering_actuator=actuator),
        inbox,
        threading.Event(),
        InboxOverflow(),
        0.1,
        1.0,
    )

    assert failed is True
    assert [command.reason for command in actuator.commands[-2:]] == [
        SteeringCommandReason.RUNTIME_FAULT,
        SteeringCommandReason.SHUTDOWN,
    ]
    assert all(command.assistance == 0.0 for command in actuator.commands[-2:])


def test_failure_during_live_fallback_is_recorded_once_before_shutdown() -> None:
    inbox: queue.Queue[KernelInput] = queue.Queue()
    inbox.put(CanReaderFailed(CanNetwork.FCAN, 1.0, "receive failed"))
    actuator = FailingFallbackActuator()
    kernel = RecordingKernel()

    failed = run_coordinator_loop(
        kernel,
        EffectExecutor(steering_actuator=actuator),
        inbox,
        threading.Event(),
        InboxOverflow(),
        0.1,
        1.0,
    )

    assert failed is True
    assert any(isinstance(item, SteeringActuatorFailed) for item in kernel.inputs)
    assert kernel.health.steering_actuator_fault is not None
    assert kernel.health.steering_actuator_fault.message == "failed attempt 2"
    assert actuator.attempts == 3


def test_inbox_overflow_commands_fallback_before_shutdown() -> None:
    overflow = InboxOverflow()
    assert overflow.latch(CanNetwork.KCAN, 1.0, 1) is True
    actuator = RecordingActuator()

    failed = run_coordinator_loop(
        CoordinatorKernel(),
        EffectExecutor(steering_actuator=actuator),
        queue.Queue(),
        threading.Event(),
        overflow,
        0.1,
        1.0,
    )

    assert failed is True
    assert [command.reason for command in actuator.commands[-2:]] == [
        SteeringCommandReason.RUNTIME_FAULT,
        SteeringCommandReason.SHUTDOWN,
    ]


def test_default_live_composition_emits_no_startup_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSocketCanBus.instances = []
    monkeypatch.setattr(live, "SocketCanBus", FakeSocketCanBus)
    monkeypatch.setattr(live, "run_coordinator_loop", start_kernel_then_stop)

    assert live.run_live(default_config()) == 0

    assert all(not bus.sent for bus in FakeSocketCanBus.instances)


def test_explicit_kcan_tx_composition_emits_rate_limited_startup_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSocketCanBus.instances = []
    monkeypatch.setattr(live, "SocketCanBus", FakeSocketCanBus)
    monkeypatch.setattr(live, "run_coordinator_loop", start_kernel_then_stop)

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
