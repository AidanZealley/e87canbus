"""Single-owner coordinator kernel shared by simulated and live runners."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import assert_never

from e87canbus.application.controller import (
    ApplicationSnapshot,
    initial_effects,
    normalize_state,
    snapshot,
    steering_command_for_active_curve,
    transition,
)
from e87canbus.application.events import (
    ApplicationEffect,
    ApplicationEvent,
    ControlTimerElapsed,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.application.state import ApplicationState
from e87canbus.config import CanNetwork, SteeringConfig
from e87canbus.features.steering import (
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    initial_active_steering_curve,
    steering_curve_fingerprint,
    validate_active_steering_curve,
    validate_steering_curve_definition,
)
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
class TimerElapsed:
    now: float


@dataclass(frozen=True)
class CanReaderFailed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class CanEffectExecutionFailed:
    network: CanNetwork
    failed_at: float
    message: str


@dataclass(frozen=True)
class SteeringActuatorFailed:
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


@dataclass(frozen=True)
class ActivateSteeringCurve:
    definition: SteeringCurveDefinition
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = None


KernelInput = (
    KernelStarted
    | ReceivedCanFrame
    | TimerElapsed
    | CanReaderFailed
    | CanEffectExecutionFailed
    | SteeringActuatorFailed
    | InboxOverflowed
    | ShutdownRequested
    | ActivateSteeringCurve
)


class KernelLifecycle(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"


class RuntimeFaultKind(StrEnum):
    CAN_READER = "can_reader"
    CAN_EFFECT_EXECUTION = "can_effect_execution"
    STEERING_ACTUATOR = "steering_actuator"
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
    steering_actuator_fault: RuntimeFault | None = None

    def for_network(self, network: CanNetwork) -> NetworkRuntimeHealth:
        return next(item for item in self.networks if item.network is network)

    @property
    def fatal(self) -> bool:
        return self.steering_actuator_fault is not None or any(
            item.fault is not None for item in self.networks
        )

    def with_fault(self, network: CanNetwork, fault: RuntimeFault) -> RuntimeHealth:
        return self._replace(replace(self.for_network(network), fault=fault))

    def _replace(self, replacement: NetworkRuntimeHealth) -> RuntimeHealth:
        return RuntimeHealth(
            networks=tuple(
                replacement if item.network is replacement.network else item
                for item in self.networks
            ),
            steering_actuator_fault=self.steering_actuator_fault,
        )

    def with_steering_actuator_fault(self, fault: RuntimeFault) -> RuntimeHealth:
        return replace(self, steering_actuator_fault=fault)


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
        active_steering_curve: ActiveSteeringCurve | None = None,
    ) -> None:
        self._steering_config = steering_config or SteeringConfig()
        self._state = normalize_state(
            state or ApplicationState(),
            self._steering_config,
        )
        self._router = router or ProtocolRouter()
        self._active_steering_curve = (
            active_steering_curve or initial_active_steering_curve()
        )
        validate_active_steering_curve(self._active_steering_curve)
        self._steering_curve_activation_status = SteeringCurveActivationStatus.ACTIVE
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
        return snapshot(
            self._state,
            self._steering_config,
            self._active_steering_curve,
            self._steering_curve_activation_status,
        )

    def diagnostics(self) -> DiagnosticSnapshot:
        return DiagnosticSnapshot(self._lifecycle, self._revision, self._health)

    def dispatch(self, kernel_input: KernelInput) -> Commit | None:
        """Accept the kernel's only state-changing input path."""

        if (
            self._lifecycle is KernelLifecycle.STOPPED
            and not isinstance(
                kernel_input,
                (CanEffectExecutionFailed, SteeringActuatorFailed, ShutdownRequested),
            )
        ):
            return None

        match kernel_input:
            case ShutdownRequested():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    self._lifecycle = KernelLifecycle.STOPPED
                    return None
                commit = self._transition(
                    SteeringFallbackRequested(SteeringFallbackReason.SHUTDOWN)
                )
                self._lifecycle = KernelLifecycle.STOPPED
                return commit
            case KernelStarted():
                if self._lifecycle is not KernelLifecycle.CREATED:
                    return None
                self._lifecycle = KernelLifecycle.RUNNING
                return self._commit_startup()
            case CanReaderFailed(network, failed_at, message):
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(RuntimeFaultKind.CAN_READER, failed_at, message),
                )
                return self._transition(
                    SteeringFallbackRequested(
                        SteeringFallbackReason.CAN_READER_FAILURE
                    )
                )
            case InboxOverflowed(network, failed_at, message):
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(RuntimeFaultKind.INBOX_OVERFLOW, failed_at, message),
                )
                return self._transition(
                    SteeringFallbackRequested(SteeringFallbackReason.INBOX_OVERFLOW)
                )
            case CanEffectExecutionFailed(network, failed_at, message):
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(
                        RuntimeFaultKind.CAN_EFFECT_EXECUTION,
                        failed_at,
                        message,
                    ),
                )
                return None
            case SteeringActuatorFailed(failed_at, message):
                self._health = self._health.with_steering_actuator_fault(
                    RuntimeFault(
                        RuntimeFaultKind.STEERING_ACTUATOR,
                        failed_at,
                        message,
                    )
                )
                return None
            case ReceivedCanFrame():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._receive(kernel_input)
            case TimerElapsed(now):
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._transition(ControlTimerElapsed(now))
            case ActivateSteeringCurve():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._activate_steering_curve(kernel_input)
            case _:
                assert_never(kernel_input)

    def _receive(self, received: ReceivedCanFrame) -> Commit | None:
        routed = RoutedCanFrame(network=received.network, frame=received.frame)
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
        result = transition(
            self._state,
            event,
            self._steering_config,
            self._active_steering_curve.definition,
        )
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
            effects=initial_effects(
                self._state,
                self._steering_config,
                self._active_steering_curve.definition,
            ),
            state_changed=True,
        )

    def _activate_steering_curve(self, request: ActivateSteeringCurve) -> Commit:
        validate_steering_curve_definition(request.definition)
        current = self._active_steering_curve
        fingerprint = steering_curve_fingerprint(request.definition)
        definition_changed = fingerprint != current.fingerprint
        next_active = ActiveSteeringCurve(
            definition=request.definition,
            fingerprint=fingerprint,
            activation_revision=(
                current.activation_revision + 1
                if definition_changed
                else current.activation_revision
            ),
            saved_profile_id=request.saved_profile_id,
            saved_profile_revision=request.saved_profile_revision,
        )
        previous_snapshot = self.snapshot()
        self._active_steering_curve = next_active
        self._steering_curve_activation_status = SteeringCurveActivationStatus.ACTIVE
        self._revision += 1
        effects: tuple[ApplicationEffect, ...] = ()
        if definition_changed:
            command = steering_command_for_active_curve(
                self._state,
                self._steering_config,
                request.definition,
            )
            if command is not None:
                effects = (command,)
        committed_snapshot = self.snapshot()
        return Commit(
            revision=self._revision,
            snapshot=committed_snapshot,
            effects=effects,
            state_changed=committed_snapshot != previous_snapshot,
        )
