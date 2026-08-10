from __future__ import annotations

import time
from queue import Empty, Queue

from e87canbus.console.service import ConsoleCanService
from e87canbus.protocol.can import CanFrame


class FakeReceiver:
    def __init__(self) -> None:
        self.items: Queue[CanFrame | Exception] = Queue()
        self.closed = False

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        try:
            item = self.items.get(timeout=timeout_s)
        except Empty:
            return None
        if isinstance(item, Exception):
            raise item
        return item

    def shutdown(self) -> None:
        self.closed = True


def wait_until(predicate, timeout_s: float = 1.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        time.sleep(0.005)


def test_counts_every_received_frame_without_retaining_raw_content() -> None:
    receiver = FakeReceiver()
    notifications = []
    service = ConsoleCanService(lambda: receiver)
    service.start(notifications.append)
    receiver.items.put(CanFrame(0x123, b"secret payload"))
    receiver.items.put(CanFrame(0x456, b"\x01\x02"))

    wait_until(lambda: service.snapshot().frames_received == 2)
    snapshot = service.snapshot()
    service.stop()

    assert snapshot.connected is True
    assert snapshot.fault is None
    assert snapshot.revision == 3
    assert not hasattr(snapshot, "frame")
    assert receiver.closed is True
    assert [item.frames_received for item in notifications] == [0, 1, 2]


def test_reader_fault_is_reported_and_clean_shutdown_closes_the_receiver() -> None:
    receiver = FakeReceiver()
    service = ConsoleCanService(lambda: receiver)
    service.start(lambda _snapshot: None)
    receiver.items.put(OSError("adapter gone"))

    wait_until(lambda: service.snapshot().fault is not None)
    snapshot = service.snapshot()
    assert receiver.closed is True
    service.stop()

    assert snapshot.connected is False
    assert snapshot.frames_received == 0
    assert snapshot.fault == "kcan receive failed: adapter gone"
    assert receiver.closed is True


def test_open_failure_is_bounded_state_instead_of_a_transmit_fallback() -> None:
    def fail_open() -> FakeReceiver:
        raise OSError("interface missing")

    service = ConsoleCanService(fail_open)
    service.start(lambda _snapshot: None)
    snapshot = service.snapshot()
    service.stop()

    assert snapshot.connected is False
    assert snapshot.frames_received == 0
    assert snapshot.fault == "failed to open kcan: interface missing"
    assert service.ready is False


def test_publication_listener_failure_does_not_stop_can_receipt() -> None:
    receiver = FakeReceiver()

    def broken_listener(_snapshot) -> None:
        raise OSError("browser path unavailable")

    service = ConsoleCanService(lambda: receiver)
    service.start(broken_listener)
    receiver.items.put(CanFrame(0x111, b"one"))
    receiver.items.put(CanFrame(0x222, b"two"))

    wait_until(lambda: service.snapshot().frames_received == 2)
    service.stop()

    assert service.snapshot().frames_received == 2
