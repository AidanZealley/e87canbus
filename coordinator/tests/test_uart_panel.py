from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from e87canbus.adapters.uart_panel import UartPanel
from e87canbus.local_controls.model import (
    CoordinatorCondition,
    CoordinatorConditionChanged,
    HotspotLifecycle,
    HotspotObserved,
    LocalControlsEvent,
    PanelAdapterFailed,
    PanelButtonPressed,
    PanelDisplayState,
    PanelLink,
    PanelLinkChanged,
)
from e87canbus.local_controls.ports import LocalControlsInputSink
from e87canbus.local_controls.service import LocalControlsService


class FakeSerial:
    def __init__(self) -> None:
        self.received: deque[bytes | BaseException] = deque()
        self.written = bytearray()
        self.write_limit: int | None = None
        self.write_error: OSError | None = None
        self.blocked_writes = 0
        self.write_calls = 0
        self.closed = False

    def read(self, size: int) -> bytes:
        if not self.received:
            raise BlockingIOError
        item = self.received.popleft()
        if isinstance(item, BaseException):
            raise item
        chunk, remainder = item[:size], item[size:]
        if remainder:
            self.received.appendleft(remainder)
        return chunk

    def write(self, data: bytes) -> int:
        self.write_calls += 1
        if self.blocked_writes:
            self.blocked_writes -= 1
            raise BlockingIOError
        if self.write_error is not None:
            raise self.write_error
        length = len(data) if self.write_limit is None else min(len(data), self.write_limit)
        self.written.extend(data[:length])
        return length

    def close(self) -> None:
        self.closed = True


class FakeOpener:
    def __init__(self, *results: FakeSerial | OSError) -> None:
        self.results = deque(results)
        self.devices: list[str] = []

    def __call__(self, device: str) -> FakeSerial:
        self.devices.append(device)
        result = self.results.popleft()
        if isinstance(result, OSError):
            raise result
        return result


class EventSink:
    def __init__(self) -> None:
        self.events: list[LocalControlsEvent] = []
        self.accept = True

    def __call__(self, event: LocalControlsEvent) -> bool:
        self.events.append(event)
        return self.accept


def test_connects_nonblocking_and_sends_latest_complete_state() -> None:
    serial = FakeSerial()
    opener = FakeOpener(serial)
    sink = EventSink()
    panel = UartPanel(opener=opener)
    panel.start(sink)
    panel.set_display(PanelDisplayState.READY)

    panel.poll(10.0)

    assert opener.devices == ["/dev/serial0"]
    assert serial.written == b"PANEL 1 STATE ready\n"
    assert sink.events == [PanelLinkChanged(PanelLink.CONNECTED)]
    assert panel.diagnostics.successful_connections == 1
    assert panel.diagnostics.link is PanelLink.CONNECTED


def test_hello_refreshes_state_and_starts_a_new_button_sequence_session() -> None:
    serial = FakeSerial()
    serial.received.append(
        b"PANEL 1 BUTTON 4294967295\n"
        b"PANEL 1 BUTTON 4294967295\n"
        b"PANEL 1 BUTTON 0\n"
        b"PANEL 1 HELLO\n"
        b"PANEL 1 BUTTON 0\n"
    )
    sink = EventSink()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(sink)

    panel.poll(1.0)

    assert sink.events == [
        PanelLinkChanged(PanelLink.CONNECTED),
        PanelButtonPressed(1),
        PanelButtonPressed(2),
        PanelButtonPressed(3),
    ]
    assert serial.written == b"PANEL 1 STATE starting\n"


def test_rejected_button_observation_does_not_consume_its_sequence() -> None:
    serial = FakeSerial()
    sink = EventSink()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(sink)
    panel.poll(1.0)
    sink.events.clear()
    sink.accept = False
    serial.received.append(b"PANEL 1 BUTTON 7\n")

    panel.poll(2.0)
    sink.accept = True
    panel.poll(3.0)

    assert sink.events == [PanelButtonPressed(1), PanelButtonPressed(1)]


def test_later_presses_are_not_reordered_around_a_pending_press() -> None:
    serial = FakeSerial()
    sink = EventSink()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(sink)
    panel.poll(1.0)
    sink.events.clear()
    sink.accept = False
    serial.received.append(b"PANEL 1 BUTTON 7\nPANEL 1 BUTTON 8\n")

    panel.poll(2.0)
    sink.accept = True
    panel.poll(3.0)
    serial.received.append(b"PANEL 1 BUTTON 8\nPANEL 1 BUTTON 9\n")
    panel.poll(4.0)

    assert sink.events == [
        PanelButtonPressed(1),
        PanelButtonPressed(1),
        PanelButtonPressed(2),
    ]


def test_malformed_and_oversized_input_is_bounded_and_ignored() -> None:
    serial = FakeSerial()
    serial.received.append(
        (
            b"PANEL 2 BUTTON 1\n"
            b"PANEL 1 BUTTON -1\n"
            b"PANEL 1 BUTTON 4294967296\n"
            b"PANEL 1 WAT 2\n"
            b"PANEL 1 BUTTON \xff\n"
        )
        + b"x" * 65
        + b"PANEL 1 BUTTON 8\n"
        + b"\nPANEL 1 BUTTON 9\n"
    )
    sink = EventSink()
    panel = UartPanel(max_line_bytes=64, opener=FakeOpener(serial))
    panel.start(sink)

    panel.poll(1.0)

    assert sink.events == [
        PanelLinkChanged(PanelLink.CONNECTED),
        PanelButtonPressed(1),
    ]
    assert panel.diagnostics.invalid_lines == 5
    assert panel.diagnostics.oversized_lines == 1


def test_read_work_is_bounded_per_poll() -> None:
    serial = FakeSerial()
    serial.received.append(b"PANEL 1 BUTTON 1\nPANEL 1 BUTTON 2\n")
    sink = EventSink()
    panel = UartPanel(read_budget_bytes=17, opener=FakeOpener(serial))
    panel.start(sink)

    panel.poll(1.0)
    assert sink.events == [
        PanelLinkChanged(PanelLink.CONNECTED),
        PanelButtonPressed(1),
    ]

    panel.poll(2.0)
    assert sink.events == [
        PanelLinkChanged(PanelLink.CONNECTED),
        PanelButtonPressed(1),
        PanelButtonPressed(2),
    ]


def test_open_failure_is_reported_with_a_bound_and_reconnects() -> None:
    serial = FakeSerial()
    opener = FakeOpener(OSError("x" * 300), serial)
    sink = EventSink()
    panel = UartPanel(reconnect_interval_s=1.0, opener=opener)
    panel.start(sink)

    panel.poll(10.0)
    assert len(sink.events) == 1
    failure = sink.events[0]
    assert isinstance(failure, PanelAdapterFailed)
    assert len(failure.message) == 160
    assert panel.diagnostics.link is PanelLink.DISCONNECTED

    panel.poll(10.9)
    assert len(opener.devices) == 1
    panel.poll(11.0)

    assert opener.devices == ["/dev/serial0", "/dev/serial0"]
    assert sink.events[-1] == PanelLinkChanged(PanelLink.CONNECTED)
    assert serial.written == b"PANEL 1 STATE starting\n"
    assert panel.diagnostics.last_error is None


def test_write_failure_disconnects_and_retries_the_failure_observation() -> None:
    first = FakeSerial()
    second = FakeSerial()
    sink = EventSink()
    panel = UartPanel(reconnect_interval_s=1.0, opener=FakeOpener(first, second))
    panel.start(sink)
    panel.poll(10.0)
    sink.events.clear()

    sink.accept = False
    first.write_error = OSError("device lost")
    panel.set_display(PanelDisplayState.FAULT)
    assert first.closed
    assert sink.events == []

    sink.accept = True
    panel.poll(10.5)
    assert isinstance(sink.events[-1], PanelAdapterFailed)
    panel.poll(11.0)

    assert sink.events[-1] == PanelLinkChanged(PanelLink.CONNECTED)
    assert second.written == b"PANEL 1 STATE fault\n"


def test_reconnect_accepts_reused_wire_sequence_when_hello_was_missed() -> None:
    first = FakeSerial()
    first.received.extend(
        [
            b"PANEL 1 BUTTON 1\n",
            OSError("device lost"),
        ]
    )
    second = FakeSerial()
    second.received.append(b"PANEL 1 BUTTON 1\n")
    sink = EventSink()
    panel = UartPanel(
        reconnect_interval_s=1.0,
        opener=FakeOpener(first, second),
    )
    panel.start(sink)

    panel.poll(10.0)
    panel.poll(11.0)

    assert [
        event.sequence for event in sink.events if isinstance(event, PanelButtonPressed)
    ] == [1, 2]
    assert any(isinstance(event, PanelAdapterFailed) for event in sink.events)


def test_partial_writes_complete_one_line_and_coalesce_later_states() -> None:
    serial = FakeSerial()
    serial.write_limit = 5
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(EventSink())
    panel.poll(1.0)

    panel.set_display(PanelDisplayState.READY)
    panel.set_display(PanelDisplayState.FAULT)
    for now in range(2, 20):
        panel.poll(float(now))

    assert bytes(serial.written) == (
        b"PANEL 1 STATE starting\n" b"PANEL 1 STATE fault\n"
    )


def test_close_uses_a_bounded_drain_to_complete_off_after_backpressure() -> None:
    serial = FakeSerial()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(EventSink())
    panel.poll(1.0)
    serial.write_limit = 3
    serial.blocked_writes = 2

    panel.set_display(PanelDisplayState.OFF)
    panel.close()

    assert bytes(serial.written) == (
        b"PANEL 1 STATE starting\n" b"PANEL 1 STATE off\n"
    )
    assert serial.closed


def test_close_does_not_wait_indefinitely_for_a_nonwritable_uart() -> None:
    serial = FakeSerial()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(EventSink())
    panel.poll(1.0)
    calls_before_off = serial.write_calls
    serial.blocked_writes = 100

    panel.set_display(PanelDisplayState.OFF)
    panel.close()

    assert serial.write_calls - calls_before_off == 65
    assert serial.closed


def test_close_is_idempotent() -> None:
    serial = FakeSerial()
    panel = UartPanel(opener=FakeOpener(serial))
    panel.start(EventSink())
    panel.poll(1.0)

    panel.close()
    panel.close()

    assert serial.closed
    assert panel.diagnostics.link is PanelLink.DISCONNECTED


class ServiceHotspot:
    def __init__(self) -> None:
        self.activations = 0
        self.deactivations = 0

    def start(self, submit: LocalControlsInputSink) -> None:
        del submit

    def activate(self) -> None:
        self.activations += 1

    def deactivate(self) -> None:
        self.deactivations += 1

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        pass


class ServiceCondition:
    def start(self, submit: LocalControlsInputSink) -> None:
        del submit

    def poll(self, now: float) -> None:
        del now

    def close(self) -> None:
        pass


def test_firmware_sequence_restart_remains_distinct_to_the_service() -> None:
    serial = FakeSerial()
    panel = UartPanel(opener=FakeOpener(serial))
    hotspot = ServiceHotspot()
    service = LocalControlsService(
        panel=panel,
        hotspot=hotspot,
        coordinator_condition=ServiceCondition(),
        poll_interval_s=0.005,
        panel_refresh_interval_s=10.0,
    )
    service.start()
    try:
        service.submit(
            CoordinatorConditionChanged(CoordinatorCondition.READY)
        ).result(timeout=1.0)
        _wait_until(lambda: panel.diagnostics.link is PanelLink.CONNECTED)

        serial.received.append(b"PANEL 1 BUTTON 1\n")
        _wait_until(lambda: hotspot.activations == 1)
        assert service.snapshot().state.last_button_sequence == 1

        service.submit(HotspotObserved(HotspotLifecycle.ACTIVE)).result(timeout=1.0)
        serial.received.append(b"PANEL 1 HELLO\nPANEL 1 BUTTON 1\n")
        _wait_until(lambda: hotspot.deactivations == 1)
        assert service.snapshot().state.last_button_sequence == 2
    finally:
        service.stop()


def _wait_until(predicate: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 1.0
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("condition was not reached")
        time.sleep(0.005)
