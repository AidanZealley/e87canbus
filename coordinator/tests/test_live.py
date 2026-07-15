import logging
import queue
import threading
import time
from dataclasses import replace

import e87canbus.live as live
import pytest
from e87canbus.composition import (
    ControllerMode,
    build_controller_service,
    live_selection,
)
from e87canbus.config import CanNetwork, default_config, simulator_config
from e87canbus.live import InboxOverflow, read_frames_into_queue
from e87canbus.protocol.can import CanFrame
from e87canbus.runtime import (
    CanReaderFailed,
    ControllerInput,
    ReceivedCanFrame,
)
from e87canbus.service import ControllerServiceError, ControllerServiceLifecycle


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


class FakeSocketCanBus:
    instances: list["FakeSocketCanBus"] = []

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self.sent: list[CanFrame] = []
        self.instances.append(self)

    def send(self, frame: CanFrame) -> None:
        self.sent.append(frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        time.sleep(min(timeout_s or 0.0, 0.001))
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


class CleanupFailingSocketCanBus(FakeSocketCanBus):
    shutdown_interfaces: list[str] = []
    fail_open_interface: str | None = None
    fail_shutdown_interface: str | None = None

    def __init__(self, interface: str) -> None:
        if interface == self.fail_open_interface:
            raise OSError("open failed")
        super().__init__(interface)

    def shutdown(self) -> None:
        self.shutdown_interfaces.append(self.interface)
        if self.interface == self.fail_shutdown_interface:
            raise OSError("shutdown failed")


class StubbornSocketCanBus(FakeSocketCanBus):
    instances: list["StubbornSocketCanBus"] = []

    def __init__(self, interface: str) -> None:
        super().__init__(interface)
        self.release = threading.Event()

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        self.release.wait()
        return None

    def shutdown(self) -> None:
        # Deliberately fail to unblock receive so shutdown verification must detect the reader.
        pass


def test_reader_timestamps_frame_at_receive_and_stops() -> None:
    bus = BlockingFakeBus()
    inbox: queue.Queue[ControllerInput] = queue.Queue()
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
    inbox: queue.Queue[ControllerInput] = queue.Queue()
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
    inbox: queue.Queue[ControllerInput] = queue.Queue()
    stop = threading.Event()
    for _ in range(live.MAX_CONSECUTIVE_READER_ERRORS):
        bus.received.put(OSError("receive failed"))

    read_frames_into_queue(CanNetwork.FCAN, bus, inbox, stop, InboxOverflow())

    failure = inbox.get_nowait()
    assert isinstance(failure, CanReaderFailed)
    assert failure.network is CanNetwork.FCAN
    assert failure.message == "receive failed"
    assert inbox.empty()


def test_canonical_live_service_reports_queue_latency_without_rewriting_ingress_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = MutableClock(2.0)
    config = replace(
        default_config(),
        can_networks=tuple(replace(item, enabled=False) for item in default_config().can_networks),
        tick_interval_s=10.0,
        runtime_queue_latency_warning_s=1.0,
    )
    service = build_controller_service(ControllerMode.LIVE, config=config, clock=clock)

    with caplog.at_level(logging.WARNING):
        service.start()
        service.submit(
            ReceivedCanFrame(CanNetwork.FCAN, CanFrame(0x123, b"\x01"), 0.5)
        ).result(timeout=0.2)
        service.stop()

    assert "network=fcan latency_s=1.500" in caplog.text


def test_default_live_composition_emits_no_startup_frames() -> None:
    FakeSocketCanBus.instances = []
    service = build_controller_service(
        ControllerMode.LIVE,
        socketcan_factory=FakeSocketCanBus,
    )

    service.start()
    service.stop()

    assert all(not bus.sent for bus in FakeSocketCanBus.instances)


def test_explicit_kcan_tx_composition_emits_rate_limited_startup_frames() -> None:
    FakeSocketCanBus.instances = []
    config = simulator_config()
    selection = replace(
        live_selection(config),
        tx_grants=frozenset({CanNetwork.KCAN}),
    )
    service = build_controller_service(
        ControllerMode.LIVE,
        config=config,
        selection=selection,
        socketcan_factory=FakeSocketCanBus,
    )

    service.start()
    service.stop()

    kcan = next(bus for bus in FakeSocketCanBus.instances if bus.interface == "can0")
    assert kcan.sent == [CanFrame(0x701, b"\x03\x00\x00\x00\x00\x00\x00\x00")]


def test_live_inbox_overflow_stops_once_cleans_up_and_returns_nonzero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    FakeSocketCanBus.instances = []
    config = replace(default_config(), runtime_inbox_capacity=1, tick_interval_s=0.01)
    service = build_controller_service(
        ControllerMode.LIVE,
        config=config,
        socketcan_factory=OverflowingSocketCanBus,
    )

    with caplog.at_level(logging.ERROR):
        service.start()
        deadline = time.monotonic() + 1.0
        while service.lifecycle is not ControllerServiceLifecycle.STOPPED:
            assert time.monotonic() < deadline
        service.stop()

    assert service.snapshot().diagnostics.health.fatal is True
    assert caplog.text.count("live CAN inbox overflow") == 1
    assert "network=kcan capacity=1" in caplog.text
    assert all(
        isinstance(bus, OverflowingSocketCanBus) and bus.shutdown_called
        for bus in FakeSocketCanBus.instances
    )


def test_partial_open_cleanup_keeps_original_failure_when_shutdown_also_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    FakeSocketCanBus.instances = []
    CleanupFailingSocketCanBus.shutdown_interfaces = []
    CleanupFailingSocketCanBus.fail_open_interface = "can1"
    CleanupFailingSocketCanBus.fail_shutdown_interface = "can0"
    service = build_controller_service(
        ControllerMode.LIVE,
        socketcan_factory=CleanupFailingSocketCanBus,
    )

    with caplog.at_level(logging.ERROR), pytest.raises(OSError, match="open failed"):
        service.start()

    assert CleanupFailingSocketCanBus.shutdown_interfaces == ["can0"]
    assert "failed to close SocketCAN network kcan" in caplog.text


def test_final_cleanup_isolates_each_interface_and_reports_close_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    FakeSocketCanBus.instances = []
    CleanupFailingSocketCanBus.shutdown_interfaces = []
    CleanupFailingSocketCanBus.fail_open_interface = None
    CleanupFailingSocketCanBus.fail_shutdown_interface = "can0"
    service = build_controller_service(
        ControllerMode.LIVE,
        socketcan_factory=CleanupFailingSocketCanBus,
    )

    with caplog.at_level(logging.ERROR):
        service.start()
        service.stop()

    assert CleanupFailingSocketCanBus.shutdown_interfaces == ["can0", "can1", "can2"]
    assert "failed to close SocketCAN network kcan" in caplog.text


def test_live_shutdown_surfaces_a_reader_that_remains_blocked_after_adapter_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    StubbornSocketCanBus.instances = []
    monkeypatch.setattr(live, "READER_JOIN_TIMEOUT_S", 0.01)
    service = build_controller_service(
        ControllerMode.LIVE,
        socketcan_factory=StubbornSocketCanBus,
    )
    service.start()

    try:
        with pytest.raises(
            ControllerServiceError,
            match="live CAN readers did not stop after adapter close",
        ):
            service.stop()
    finally:
        for bus in StubbornSocketCanBus.instances:
            bus.release.set()

    deadline = time.monotonic() + 1.0
    while any(
        thread.is_alive()
        for thread in threading.enumerate()
        if thread.name.endswith("-reader")
    ):
        assert time.monotonic() < deadline
