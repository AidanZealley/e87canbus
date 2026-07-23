"""Immutable runtime-health diagnostics owned by the kernel.

Health is a separate service projection from application state: it records
adapter and transport faults and per-network frame outcomes without ever
mutating the authoritative controller state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from e87canbus.config import CanNetwork
from e87canbus.domain.device import DeviceRole


class RuntimeFaultKind(StrEnum):
    CAN_READER = "can_reader"
    CAN_EFFECT_EXECUTION = "can_effect_execution"
    STEERING_ACTUATOR = "steering_actuator"
    INBOX_OVERFLOW = "inbox_overflow"
    DEVICE_ADAPTER = "device_adapter"


@dataclass(frozen=True)
class RuntimeFault:
    kind: RuntimeFaultKind
    occurred_at: float
    message: str


@dataclass(frozen=True)
class NetworkRuntimeHealth:
    network: CanNetwork
    fault: RuntimeFault | None = None
    received_frames: int = 0
    decoded_frames: int = 0
    ignored_frames: int = 0
    malformed_frames: int = 0


@dataclass(frozen=True)
class DeviceRuntimeHealth:
    role: DeviceRole
    fault: RuntimeFault | None = None


def _empty_network_health() -> tuple[NetworkRuntimeHealth, ...]:
    return tuple(NetworkRuntimeHealth(network) for network in CanNetwork)


@dataclass(frozen=True)
class RuntimeHealth:
    networks: tuple[NetworkRuntimeHealth, ...] = field(default_factory=_empty_network_health)
    steering_actuator_fault: RuntimeFault | None = None
    inbox_overflow_fault: RuntimeFault | None = None
    devices: tuple[DeviceRuntimeHealth, ...] = tuple(
        DeviceRuntimeHealth(role) for role in DeviceRole
    )

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

    def with_steering_actuator_fault(self, fault: RuntimeFault) -> RuntimeHealth:
        return replace(self, steering_actuator_fault=fault)

    def with_inbox_overflow(
        self,
        network: CanNetwork | None,
        fault: RuntimeFault,
    ) -> RuntimeHealth:
        updated = replace(self, inbox_overflow_fault=fault)
        return updated if network is None else updated.with_fault(network, fault)

    def with_device_fault(self, role: DeviceRole, fault: RuntimeFault) -> RuntimeHealth:
        return replace(
            self,
            devices=tuple(
                replace(item, fault=fault) if item.role is role else item for item in self.devices
            ),
        )

    def with_frame_outcome(self, network: CanNetwork, outcome: str) -> RuntimeHealth:
        current = self.for_network(network)
        if outcome == "decoded":
            updated = replace(
                current,
                received_frames=current.received_frames + 1,
                decoded_frames=current.decoded_frames + 1,
            )
        elif outcome == "ignored":
            updated = replace(
                current,
                received_frames=current.received_frames + 1,
                ignored_frames=current.ignored_frames + 1,
            )
        elif outcome == "malformed":
            updated = replace(
                current,
                received_frames=current.received_frames + 1,
                malformed_frames=current.malformed_frames + 1,
            )
        else:
            raise ValueError(f"unsupported frame outcome: {outcome}")
        return self._replace(updated)
