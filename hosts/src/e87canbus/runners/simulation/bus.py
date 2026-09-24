"""In-memory CAN broadcast for vehicle simulation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from e87canbus.adapters.can_io import CanEndpoint
from e87canbus.protocol.can import CanFrame


@dataclass
class _InMemoryCanBus:
    name: str
    network: InMemoryCanNetwork
    _received: deque[CanFrame] = field(default_factory=deque)

    def send(self, frame: CanFrame) -> None:
        self.network._send(self.name, frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        return self._received.popleft() if self._received else None

    def _enqueue(self, frame: CanFrame) -> None:
        self._received.append(frame)


class InMemoryCanNetwork:
    """Broadcast vehicle frames to the other endpoints on one CAN network."""

    def __init__(self) -> None:
        self._buses: dict[str, _InMemoryCanBus] = {}

    def create_bus(self, name: str) -> CanEndpoint:
        if name in self._buses:
            raise ValueError(f"bus already exists: {name}")
        bus = _InMemoryCanBus(name=name, network=self)
        self._buses[name] = bus
        return bus

    def _send(self, source: str, frame: CanFrame) -> None:
        for name, bus in self._buses.items():
            if name != source:
                bus._enqueue(frame)
