from __future__ import annotations

from e87canbus.adapters.coordinator_panel import UartPanelAdapter
from e87canbus.panel import CoordinatorStatus


class FakeSerialPort:
    def __init__(self) -> None:
        self.written: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def close(self) -> None:
        self.closed = True


def test_uart_adapter_sends_complete_semantic_status() -> None:
    port = FakeSerialPort()
    adapter = UartPanelAdapter(port)

    adapter.display(CoordinatorStatus.READY)

    assert port.written == [b"STATUS ready\n"]
