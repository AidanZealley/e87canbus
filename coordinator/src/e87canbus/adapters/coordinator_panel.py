"""Fixed UART transport for the physical coordinator panel."""

from __future__ import annotations

from typing import Protocol

import serial  # type: ignore[import-untyped]

from e87canbus.panel import PanelDisplay

UART_DEVICE = "/dev/ttyAMA3"
UART_BAUD_RATE = 115_200
MAXIMUM_LINE_LENGTH = 64


class SerialPort(Protocol):
    def read(self, size: int = 1) -> bytes: ...

    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


class UartPanelAdapter:
    """Send complete panel states and yield only valid, bounded button lines."""

    def __init__(self, port: SerialPort) -> None:
        self._port = port
        self._line = bytearray()
        self._discarding_line = False

    def display(self, state: PanelDisplay) -> None:
        self._port.write(f"STATUS {state.value}\n".encode("ascii"))

    def read_button_presses(self) -> int:
        presses = 0
        for value in self._port.read(MAXIMUM_LINE_LENGTH):
            if value == ord("\n"):
                if not self._discarding_line and self._line == b"BUTTON":
                    presses += 1
                self._line.clear()
                self._discarding_line = False
            elif self._discarding_line:
                continue
            elif len(self._line) < MAXIMUM_LINE_LENGTH:
                self._line.append(value)
            else:
                self._line.clear()
                self._discarding_line = True
        return presses

    def close(self) -> None:
        self._port.close()


def open_uart_panel() -> UartPanelAdapter:
    port = serial.Serial(UART_DEVICE, UART_BAUD_RATE, timeout=0.1)
    return UartPanelAdapter(port)
