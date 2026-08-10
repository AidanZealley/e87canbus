from __future__ import annotations

from e87canbus.adapters.coordinator_panel import MAXIMUM_LINE_LENGTH, UartPanelAdapter
from e87canbus.panel import PanelDisplay


class FakeSerialPort:
    def __init__(self) -> None:
        self.incoming = b""
        self.written: list[bytes] = []
        self.closed = False

    def read(self, size: int = 1) -> bytes:
        chunk, self.incoming = self.incoming[:size], self.incoming[size:]
        return chunk

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def close(self) -> None:
        self.closed = True


def test_uart_adapter_sends_complete_semantic_status() -> None:
    port = FakeSerialPort()
    adapter = UartPanelAdapter(port)

    adapter.display(PanelDisplay.HOTSPOT_CONNECTED)

    assert port.written == [b"STATUS hotspot_connected\n"]


def test_uart_adapter_accepts_button_and_discards_malformed_or_oversized_lines() -> None:
    port = FakeSerialPort()
    adapter = UartPanelAdapter(port)
    port.incoming = b"NOPE\n" + b"x" * (MAXIMUM_LINE_LENGTH + 1) + b"\nBUTTON\n"

    presses = 0
    while port.incoming:
        presses += adapter.read_button_presses()

    assert presses == 1
