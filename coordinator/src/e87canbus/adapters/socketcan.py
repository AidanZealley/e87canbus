"""SocketCAN adapter backed by python-can."""

from __future__ import annotations

from typing import Any

import can

from e87canbus.protocol.can import CanFrame


def to_python_can_message(frame: CanFrame) -> can.Message:
    return can.Message(
        arbitration_id=frame.arbitration_id,
        data=frame.data,
        is_extended_id=frame.is_extended_id,
    )


def from_python_can_message(message: can.Message) -> CanFrame:
    return CanFrame(
        arbitration_id=message.arbitration_id,
        data=bytes(message.data),
        is_extended_id=message.is_extended_id,
    )


class SocketCanBus:
    """Concrete CAN bus adapter for Linux SocketCAN interfaces."""

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self._bus = can.Bus(interface=interface, channel=interface, bustype="socketcan")

    def send(self, frame: CanFrame) -> None:
        self._bus.send(to_python_can_message(frame))

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        message = self._bus.recv(timeout=timeout_s)
        if message is None:
            return None
        return from_python_can_message(message)

    def shutdown(self) -> None:
        self._bus.shutdown()

    def __enter__(self) -> SocketCanBus:
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        self.shutdown()
