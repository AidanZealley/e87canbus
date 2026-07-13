"""Deterministic in-memory CAN networks and three-network topology."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from e87canbus.can_io import CanEndpoint
from e87canbus.config import CanNetwork
from e87canbus.protocol.can import CanFrame


@dataclass(frozen=True)
class SimulatedCanTraceEntry:
    network: CanNetwork
    source: str
    frame: CanFrame
    monotonic_s: float
    sequence: int


TraceRecorder = Callable[[CanNetwork, str, CanFrame], SimulatedCanTraceEntry]


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
    """One isolated CAN broadcast domain."""

    def __init__(
        self,
        network: CanNetwork = CanNetwork.KCAN,
        trace_capacity: int = 2_000,
        recorder: TraceRecorder | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if trace_capacity < 1:
            raise ValueError("trace_capacity must be at least 1")
        self.network = network
        self._buses: dict[str, _InMemoryCanBus] = {}
        self._trace: deque[SimulatedCanTraceEntry] = deque(maxlen=trace_capacity)
        self._sequence = 0
        self._recorder = recorder
        self._clock = clock

    def create_bus(self, name: str) -> CanEndpoint:
        if name in self._buses:
            raise ValueError(f"bus already exists on {self.network.value}: {name}")
        bus = _InMemoryCanBus(name=name, network=self)
        self._buses[name] = bus
        return bus

    def nodes(self) -> tuple[str, ...]:
        return tuple(self._buses)

    def trace(self) -> tuple[SimulatedCanTraceEntry, ...]:
        return tuple(self._trace)

    def clear_trace(self) -> None:
        self._trace.clear()
        self._sequence = 0

    def _send(self, source: str, frame: CanFrame) -> None:
        if source not in self._buses:
            raise ValueError(f"unknown bus on {self.network.value}: {source}")

        if self._recorder is None:
            self._sequence += 1
            entry = SimulatedCanTraceEntry(
                network=self.network,
                source=source,
                frame=frame,
                monotonic_s=self._clock(),
                sequence=self._sequence,
            )
            self._trace.append(entry)
        else:
            self._recorder(self.network, source, frame)

        for name, bus in self._buses.items():
            if name != source:
                bus._enqueue(frame)


class InMemoryCanTopology:
    """Three independent broadcast domains sharing one chronological trace."""

    def __init__(
        self,
        trace_capacity: int = 2_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if trace_capacity < 1:
            raise ValueError("trace_capacity must be at least 1")
        self.trace_capacity = trace_capacity
        self._trace: deque[SimulatedCanTraceEntry] = deque(maxlen=trace_capacity)
        self._sequence = 0
        self._clock = clock
        self._networks = {
            network: InMemoryCanNetwork(
                network=network,
                trace_capacity=trace_capacity,
                recorder=self._record,
                clock=clock,
            )
            for network in CanNetwork
        }

    def create_bus(self, network: CanNetwork, name: str) -> CanEndpoint:
        return self._networks[network].create_bus(name)

    def network(self, network: CanNetwork) -> InMemoryCanNetwork:
        return self._networks[network]

    def nodes(self, network: CanNetwork) -> tuple[str, ...]:
        return self._networks[network].nodes()

    def trace(self) -> tuple[SimulatedCanTraceEntry, ...]:
        return tuple(self._trace)

    @property
    def latest_sequence(self) -> int:
        return self._sequence

    def clear_trace(self) -> None:
        self._trace.clear()
        self._sequence = 0
        for network in self._networks.values():
            network.clear_trace()

    def _record(
        self,
        network: CanNetwork,
        source: str,
        frame: CanFrame,
    ) -> SimulatedCanTraceEntry:
        self._sequence += 1
        entry = SimulatedCanTraceEntry(
            network=network,
            source=source,
            frame=frame,
            monotonic_s=self._clock(),
            sequence=self._sequence,
        )
        self._trace.append(entry)
        return entry
