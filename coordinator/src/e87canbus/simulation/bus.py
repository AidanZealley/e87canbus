"""Deterministic in-memory CAN bus simulation."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from e87canbus.protocol.can import CanBus, CanFrame


@dataclass(frozen=True)
class SimulatedCanTraceEntry:
    source: str
    frame: CanFrame
    monotonic_s: float


@dataclass
class _InMemoryCanBus:
    name: str
    network: InMemoryCanNetwork
    _received: deque[CanFrame] = field(default_factory=deque)

    def send(self, frame: CanFrame) -> None:
        self.network._send(self.name, frame)

    def receive(self, timeout_s: float | None = None) -> CanFrame | None:
        del timeout_s
        if not self._received:
            return None
        return self._received.popleft()

    def _enqueue(self, frame: CanFrame) -> None:
        self._received.append(frame)


class InMemoryCanNetwork:
    """CAN network where endpoints receive frames sent by other endpoints."""

    def __init__(self) -> None:
        self._buses: dict[str, _InMemoryCanBus] = {}
        self._trace: list[SimulatedCanTraceEntry] = []

    def create_bus(self, name: str) -> CanBus:
        if name in self._buses:
            raise ValueError(f"bus already exists: {name}")
        bus = _InMemoryCanBus(name=name, network=self)
        self._buses[name] = bus
        return bus

    def trace(self) -> tuple[SimulatedCanTraceEntry, ...]:
        return tuple(self._trace)

    def clear_trace(self) -> None:
        self._trace.clear()

    def _send(self, source: str, frame: CanFrame) -> None:
        if source not in self._buses:
            raise ValueError(f"unknown bus: {source}")

        self._trace.append(
            SimulatedCanTraceEntry(
                source=source,
                frame=frame,
                monotonic_s=time.monotonic(),
            ),
        )
        for name, bus in self._buses.items():
            if name != source:
                bus._enqueue(frame)
