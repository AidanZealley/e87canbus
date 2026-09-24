"""Immutable runtime-health diagnostics owned by the kernel.

Health is a separate service projection from application state. It records
adapter and transport faults without mutating authoritative controller state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from e87canbus.config import CanNetwork


class RuntimeFaultKind(StrEnum):
    CAN_READER = "can_reader"
    INBOX_OVERFLOW = "inbox_overflow"


@dataclass(frozen=True)
class RuntimeFault:
    kind: RuntimeFaultKind
    occurred_at: float
    message: str


@dataclass(frozen=True)
class NetworkRuntimeHealth:
    network: CanNetwork
    fault: RuntimeFault | None = None


def _empty_network_health() -> tuple[NetworkRuntimeHealth, ...]:
    return tuple(NetworkRuntimeHealth(network) for network in CanNetwork)


@dataclass(frozen=True)
class RuntimeHealth:
    networks: tuple[NetworkRuntimeHealth, ...] = field(default_factory=_empty_network_health)
    inbox_overflow_fault: RuntimeFault | None = None

    def for_network(self, network: CanNetwork) -> NetworkRuntimeHealth:
        return next(item for item in self.networks if item.network is network)

    @property
    def fatal(self) -> bool:
        return self.inbox_overflow_fault is not None or any(
            item.fault is not None for item in self.networks
        )

    def with_fault(self, network: CanNetwork, fault: RuntimeFault) -> RuntimeHealth:
        return self._replace(replace(self.for_network(network), fault=fault))

    def _replace(self, replacement: NetworkRuntimeHealth) -> RuntimeHealth:
        return replace(
            self,
            networks=tuple(
                replacement if item.network is replacement.network else item
                for item in self.networks
            ),
        )

    def with_inbox_overflow(
        self,
        network: CanNetwork | None,
        fault: RuntimeFault,
    ) -> RuntimeHealth:
        updated = replace(self, inbox_overflow_fault=fault)
        return updated if network is None else updated.with_fault(network, fault)
