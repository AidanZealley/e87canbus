"""Narrow structural capabilities for CAN I/O consumers."""

from __future__ import annotations

from typing import Protocol

from e87canbus.protocol.can import CanFrame


class CanReceiver(Protocol):
    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        """Receive one CAN frame, or None on timeout."""


class CanTransmitter(Protocol):
    def send(self, frame: CanFrame) -> None:
        """Send one CAN frame."""


class CanEndpoint(CanReceiver, CanTransmitter, Protocol):
    """Unrestricted endpoint used only by composition and external simulated nodes."""
