"""Single-owner coordinator kernel shared by simulated and live runners."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from enum import StrEnum

from e87canbus.application.controller import (
    ApplicationSnapshot,
    initial_effects,
    normalize_state,
    snapshot,
    transition,
)
from e87canbus.application.events import (
    ApplicationEffect,
    ApplicationEvent,
    ControlTimerElapsed,
)
from e87canbus.application.state import ApplicationState
from e87canbus.config import CanNetwork, SteeringConfig
from e87canbus.protocol.can import CanFrame, RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class KernelStarted:
    now: float


@dataclass(frozen=True)
class ReceivedCanFrame:
    """A CAN frame paired with its network and ingress observation time."""

    network: CanNetwork
    frame: CanFrame
    received_at: float


@dataclass(frozen=True)
class CanReaderFailed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class EffectExecutionFailed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class InboxOverflowed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class ShutdownRequested:
    now: float


KernelInput = (
    KernelStarted
    | ReceivedCanFrame
    | ControlTimerElapsed
    | CanReaderFailed
    | EffectExecutionFailed
    | InboxOverflowed
    | ShutdownRequested
)


class KernelLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


class RuntimeFaultKind(StrEnum):
    CAN_READER = "can_reader"
    EFFECT_EXECUTION = "effect_execution"
    INBOX_OVERFLOW = "inbox_overflow"


@dataclass(frozen=True)
class RuntimeFault:
    kind: RuntimeFaultKind
    occurred_at: float
    message: str


@dataclass(frozen=True)
class NetworkRuntimeHealth:
    network: CanNetwork
    latest_rx_monotonic_s: float | None = None
    fault: RuntimeFault | None = None


def _empty_network_health() -> tuple[NetworkRuntimeHealth, ...]:
    return tuple(NetworkRuntimeHealth(network) for network in CanNetwork)


@dataclass(frozen=True)
class RuntimeHealth:
    networks: tuple[NetworkRuntimeHealth, ...] = field(default_factory=_empty_network_health)

    def for_network(self, network: CanNetwork) -> NetworkRuntimeHealth:
        return next(item for item in self.networks if item.network is network)

    @property
    def fatal(self) -> bool:
        return any(item.fault is not None for item in self.networks)

    def with_receive(self, network: CanNetwork, observed_at: float) -> RuntimeHealth:
        current = self.for_network(network)
        return self._replace(replace(current, latest_rx_monotonic_s=observed_at))

    def with_fault(self, network: CanNetwork, fault: RuntimeFault) -> RuntimeHealth:
        return self._replace(replace(self.for_network(network), fault=fault))

    def _replace(self, replacement: NetworkRuntimeHealth) -> RuntimeHealth:
        return RuntimeHealth(
            tuple(
                replacement if item.network is replacement.network else item
                for item in self.networks
            )
        )


@dataclass(frozen=True)
class Commit:
    revision: int
    snapshot: ApplicationSnapshot
    effects: tuple[ApplicationEffect, ...]
    state_changed: bool


@dataclass(frozen=True)
class DiagnosticSnapshot:
    lifecycle: KernelLifecycle
    revision: int
    health: RuntimeHealth


class CoordinatorKernel:
    """Decode and commit one explicitly timed input at a time."""

    def __init__(
        self,
        state: ApplicationState | None = None,
        steering_config: SteeringConfig | None = None,
        router: ProtocolRouter | None = None,
    ) -> None:
        self._steering_config = steering_config or SteeringConfig()
        self._state = normalize_state(
            state or ApplicationState(),
            self._steering_config,
        )
        self._router = router or ProtocolRouter()
        self._revision = 0
        self._lifecycle = KernelLifecycle.CREATED
        self._health = RuntimeHealth()

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def health(self) -> RuntimeHealth:
        return self._health

    def snapshot(self) -> ApplicationSnapshot:
        return snapshot(self._state, self._steering_config)

    def diagnostics(self) -> DiagnosticSnapshot:
        return DiagnosticSnapshot(self._lifecycle, self._revision, self._health)

    def dispatch(self, kernel_input: KernelInput) -> Commit | None:
        """Accept the kernel's only state-changing input path."""

        if isinstance(kernel_input, ShutdownRequested):
            self._lifecycle = KernelLifecycle.STOPPED
            return None

        if self._lifecycle is KernelLifecycle.STOPPED:
            return None

        if isinstance(kernel_input, KernelStarted):
            if self._lifecycle is not KernelLifecycle.CREATED:
                return None
            self._lifecycle = KernelLifecycle.RUNNING
            return self._commit_startup()

        if isinstance(
            kernel_input,
            (CanReaderFailed, EffectExecutionFailed, InboxOverflowed),
        ):
            match kernel_input:
                case CanReaderFailed():
                    kind = RuntimeFaultKind.CAN_READER
                case EffectExecutionFailed():
                    kind = RuntimeFaultKind.EFFECT_EXECUTION
                case InboxOverflowed():
                    kind = RuntimeFaultKind.INBOX_OVERFLOW
            self._health = self._health.with_fault(
                kernel_input.network,
                RuntimeFault(kind, kernel_input.failed_at, kernel_input.message),
            )
            return None

        if self._lifecycle is not KernelLifecycle.RUNNING:
            return None

        if isinstance(kernel_input, ReceivedCanFrame):
            return self._receive(kernel_input)
        return self._transition(kernel_input)

    def _receive(self, received: ReceivedCanFrame) -> Commit | None:
        routed = RoutedCanFrame(network=received.network, frame=received.frame)
        self._health = self._health.with_receive(received.network, received.received_at)
        try:
            event = self._router.decode(routed, received.received_at)
        except ValueError as exc:
            LOGGER.warning(
                "ignored malformed recognized frame: network=%s id=0x%03x data=%s error=%s",
                routed.network.value,
                routed.frame.arbitration_id,
                routed.frame.data.hex(),
                exc,
            )
            return None
        return None if event is None else self._transition(event)

    def _transition(self, event: ApplicationEvent) -> Commit:
        previous_snapshot = self.snapshot()
        result = transition(self._state, event, self._steering_config)
        self._state = result.state
        self._revision += 1
        committed_snapshot = self.snapshot()
        return Commit(
            revision=self._revision,
            snapshot=committed_snapshot,
            effects=result.effects,
            state_changed=committed_snapshot != previous_snapshot,
        )

    def _commit_startup(self) -> Commit:
        self._revision = 1
        return Commit(
            revision=self._revision,
            snapshot=self.snapshot(),
            effects=initial_effects(self._state),
            state_changed=True,
        )
