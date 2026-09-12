"""Fixed UART transport for the physical coordinator panel."""

from __future__ import annotations

from typing import Protocol

import serial  # type: ignore[import-untyped]

from e87canbus.panel import CoordinatorStatus

UART_DEVICE = "/dev/ttyAMA3"
UART_BAUD_RATE = 115_200
class SerialPort(Protocol):
    def write(self, data: bytes) -> int: ...

    def close(self) -> None: ...


class UartPanelAdapter:
    """Send complete panel states."""

    def __init__(self, port: SerialPort) -> None:
        self._port = port
    def display(self, state: CoordinatorStatus) -> None:
        self._port.write(f"STATUS {state.value}\n".encode("ascii"))

    def close(self) -> None:
        self._port.close()


def open_uart_panel() -> UartPanelAdapter:
    port = serial.Serial(UART_DEVICE, UART_BAUD_RATE)
    return UartPanelAdapter(port)
