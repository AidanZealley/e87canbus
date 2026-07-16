"""Single-owner coordinator kernel shared by simulated and live runners."""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import assert_never

from e87canbus.application.controller import (
    ApplicationSnapshot,
    Transition,
    button_led_state,
    clear_maximum_assistance,
    initial_effects,
    normalize_state,
    snapshot,
    steering_command_for_active_curve,
    steering_command_for_current_state,
    transition,
)
from e87canbus.application.events import (
    ApplicationEffect,
    ApplicationEvent,
    ButtonCommandFailed,
    ButtonFeedbackDeadlineReached,
    ButtonPressed,
    ControlTimerElapsed,
    HighBeamStrobeDeadlineReached,
    MaximumAssistanceSet,
    SetButtonLeds,
    SetSteeringAssistance,
    SteeringFallbackReason,
    SteeringFallbackRequested,
    SteeringModeSet,
)
from e87canbus.application.state import ApplicationState, SteeringMode
from e87canbus.config import (
    CanNetwork,
    EngineTelemetryConfig,
    HighBeamStrobeConfig,
    SteeringConfig,
)
from e87canbus.device import DeviceLifecycleStatus, DeviceRole, DeviceSource
from e87canbus.device_registry import (
    DeviceRegistryEntry,
    FeatureUnavailable,
    RegistryHeartbeatObserved,
    RegistryHelloObserved,
    expire_entry,
    initial_registry,
    registry_entry,
    transition_heartbeat,
    transition_hello,
)
from e87canbus.features.steering import (
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    initial_active_steering_curve,
    steering_curve_fingerprint,
    validate_active_steering_curve,
    validate_steering_curve_definition,
)
from e87canbus.output import EffectRequest, OutputEffect, SendRegistryFrame
from e87canbus.protocol.can import (
    CanFrame,
    RoutedCanFrame,
    encode_welcome_ack,
)
from e87canbus.protocol.router import ProtocolRouter

LOGGER = logging.getLogger(__name__)

_controller_session_seed = secrets.randbelow(0xFFFF) + 1


def _new_controller_session_id() -> int:
    global _controller_session_seed
    session_id = _controller_session_seed
    _controller_session_seed = (_controller_session_seed % 0xFFFF) + 1
    return session_id


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
    origin_button_index: int | None = None


@dataclass(frozen=True)
class SteeringActuatorFailed:
    failed_at: float
    message: str
    origin_button_index: int | None = None


@dataclass(frozen=True)
class InboxOverflowed:
    network: CanNetwork | None
    failed_at: float
    message: str


@dataclass(frozen=True)
class DeviceAdapterFailed:
    role: DeviceRole
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
    requested_at: float = field(kw_only=True)


@dataclass(frozen=True)
class SetMaximumAssistance:
    enabled: bool

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled must be a boolean")


@dataclass(frozen=True)
class SetSteeringMode:
    mode: SteeringMode
    manual_level: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mode, SteeringMode):
            raise ValueError("mode must be a supported SteeringMode value")
        if self.manual_level is not None and (
            type(self.manual_level) is not int or self.manual_level < 0
        ):
            raise ValueError("manual_level must be a non-negative integer")


ControllerInput = (
    KernelStarted
    | ReceivedCanFrame
    | TimerElapsed
    | ButtonFeedbackDeadlineReached
    | HighBeamStrobeDeadlineReached
    | CanReaderFailed
    | CanEffectExecutionFailed
    | SteeringActuatorFailed
    | InboxOverflowed
    | DeviceAdapterFailed
    | ShutdownRequested
    | ActivateSteeringCurve
    | SetMaximumAssistance
    | SetSteeringMode
)


class StateTopic(StrEnum):
    """Closed service projection topics; not a runtime-extensible event bus."""

    VEHICLE = "vehicle"
    ENGINE = "engine"
    STEERING = "steering"
    BUTTONS = "buttons"
    LIGHTING = "lighting"
    DEVICES = "devices"
    HEALTH = "health"


INITIAL_KERNEL_TOPICS = frozenset(
    {
        StateTopic.VEHICLE,
        StateTopic.ENGINE,
        StateTopic.STEERING,
        StateTopic.BUTTONS,
        StateTopic.LIGHTING,
        StateTopic.HEALTH,
        StateTopic.DEVICES,
    }
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
        return (
            self.inbox_overflow_fault is not None
            or any(item.fault is not None for item in self.networks)
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


@dataclass(frozen=True)
class Commit:
    """One accepted transition after state mutation, with ordered desired effects.

    ``snapshot`` is the complete immutable application projection. Button output is derived from
    that application state and emitted atomically; adapter-owned device observations and immutable
    runtime diagnostics remain separate service projections rather than duplicate application
    state.
    """

    revision: int
    snapshot: ApplicationSnapshot
    effects: tuple[EffectRequest, ...]
    changed_topics: frozenset[StateTopic]
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
        engine_telemetry_config: EngineTelemetryConfig | None = None,
        high_beam_strobe_config: HighBeamStrobeConfig | None = None,
        router: ProtocolRouter | None = None,
        active_steering_curve: ActiveSteeringCurve | None = None,
        device_sources: dict[DeviceRole, DeviceSource] | None = None,
        servotronic_output_available: bool = True,
    ) -> None:
        self._steering_config = steering_config or SteeringConfig()
        self._engine_telemetry_config = engine_telemetry_config or EngineTelemetryConfig()
        self._high_beam_strobe_config = high_beam_strobe_config or HighBeamStrobeConfig()
        self._state = normalize_state(
            state or ApplicationState(),
            self._steering_config,
        )
        self._router = router or ProtocolRouter()
        self._controller_session_id = _new_controller_session_id()
        self._registry = initial_registry(device_sources)
        self._servotronic_output_available = servotronic_output_available
        self._active_steering_curve = active_steering_curve or initial_active_steering_curve()
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

    @property
    def controller_session_id(self) -> int:
        return self._controller_session_id

    @property
    def registry(self) -> tuple[DeviceRegistryEntry, ...]:
        return self._registry

    def registry_for(self, role: DeviceRole) -> DeviceRegistryEntry:
        return registry_entry(self._registry, role)

    def next_deadline(self) -> float | None:
        deadlines = [
            entry.next_deadline for entry in self._registry if entry.next_deadline is not None
        ]
        deadlines.extend(
            deadline
            for deadline in self._state.button_feedback_deadlines
            if deadline is not None
        )
        if self._state.high_beam_next_transition_at is not None:
            deadlines.append(self._state.high_beam_next_transition_at)
        return min(deadlines) if deadlines else None

    def snapshot(self) -> ApplicationSnapshot:
        return snapshot(
            self._state,
            self._steering_config,
            self._engine_telemetry_config,
            self._active_steering_curve,
            self._steering_curve_activation_status,
        )

    def diagnostics(self) -> DiagnosticSnapshot:
        return DiagnosticSnapshot(self._lifecycle, self._revision, self._health)

    def dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        """Accept the kernel's only state-changing input path."""

        if self._lifecycle is KernelLifecycle.STOPPED and not isinstance(
            kernel_input,
            (CanEffectExecutionFailed, SteeringActuatorFailed, ShutdownRequested),
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
                return self._commit_startup(kernel_input.now)
            case CanReaderFailed(network, failed_at, message):
                previous_health = self._health
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(RuntimeFaultKind.CAN_READER, failed_at, message),
                )
                return self._transition(
                    SteeringFallbackRequested(SteeringFallbackReason.CAN_READER_FAILURE),
                    previous_health=previous_health,
                )
            case InboxOverflowed(network, failed_at, message):
                previous_health = self._health
                self._health = self._health.with_inbox_overflow(
                    network,
                    RuntimeFault(RuntimeFaultKind.INBOX_OVERFLOW, failed_at, message),
                )
                return self._transition(
                    SteeringFallbackRequested(SteeringFallbackReason.INBOX_OVERFLOW),
                    previous_health=previous_health,
                )
            case DeviceAdapterFailed(role, failed_at, message):
                previous_health = self._health
                self._health = self._health.with_device_fault(
                    role,
                    RuntimeFault(RuntimeFaultKind.DEVICE_ADAPTER, failed_at, message),
                )
                if role is not DeviceRole.SERVOTRONIC_CONTROLLER:
                    return None
                previous_snapshot = self.snapshot()
                previous_button_leds = button_led_state(self._state)
                cleared = clear_maximum_assistance(self._state)
                self._state = cleared.state
                return self._commit_application_result(
                    Transition(self._state, cleared.effects),
                    previous_snapshot,
                    previous_button_leds,
                    previous_health=previous_health,
                )
            case CanEffectExecutionFailed(network, failed_at, message, origin_button_index):
                previous_health = self._health
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(
                        RuntimeFaultKind.CAN_EFFECT_EXECUTION,
                        failed_at,
                        message,
                    ),
                )
                return (
                    self._transition(
                        ButtonCommandFailed(origin_button_index, failed_at),
                        previous_health=previous_health,
                    )
                    if origin_button_index is not None
                    else None
                )
            case SteeringActuatorFailed(failed_at, message, origin_button_index):
                previous_health = self._health
                self._health = self._health.with_steering_actuator_fault(
                    RuntimeFault(
                        RuntimeFaultKind.STEERING_ACTUATOR,
                        failed_at,
                        message,
                    )
                )
                if self._lifecycle is KernelLifecycle.STOPPED:
                    return None
                previous_snapshot = self.snapshot()
                previous_button_leds = button_led_state(self._state)
                cleared = clear_maximum_assistance(self._state)
                self._state = cleared.state
                if origin_button_index is not None:
                    return self._transition(
                        ButtonCommandFailed(origin_button_index, failed_at),
                        previous_health=previous_health,
                        previous_snapshot=previous_snapshot,
                        previous_button_leds=previous_button_leds,
                        extra_effects=cleared.effects,
                    )
                return self._commit_application_result(
                    Transition(self._state, cleared.effects),
                    previous_snapshot,
                    previous_button_leds,
                    previous_health=previous_health,
                )
            case ReceivedCanFrame():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._receive(kernel_input)
            case TimerElapsed(now):
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._timer(now)
            case ButtonFeedbackDeadlineReached():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._transition(kernel_input)
            case HighBeamStrobeDeadlineReached():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._transition(kernel_input)
            case ActivateSteeringCurve():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                self._require_servotronic_available()
                return self._activate_steering_curve(kernel_input)
            case SetMaximumAssistance(enabled):
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                self._require_servotronic_available()
                return self._transition(MaximumAssistanceSet(enabled))
            case SetSteeringMode(mode, manual_level):
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                self._require_servotronic_available()
                return self._transition(SteeringModeSet(mode, manual_level))
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
            self._health = self._health.with_frame_outcome(received.network, "malformed")
            return None
        if event is None:
            self._health = self._health.with_frame_outcome(received.network, "ignored")
            return None
        self._health = self._health.with_frame_outcome(received.network, "decoded")
        if isinstance(event, RegistryHelloObserved):
            if event.payload.device_id != self.registry_for(event.role).device_id:
                LOGGER.info(
                    "ignored registry HELLO for unknown device identity: role=%s device_id=%d",
                    event.role.value,
                    event.payload.device_id,
                )
                return None
            return self._registry_hello(event)
        if isinstance(event, RegistryHeartbeatObserved):
            if event.payload.device_id != self.registry_for(event.role).device_id:
                LOGGER.info(
                    "ignored registry HEARTBEAT for unknown device identity: role=%s device_id=%d",
                    event.role.value,
                    event.payload.device_id,
                )
                return None
            return self._registry_heartbeat(event)
        if not isinstance(event, ButtonPressed):
            return self._transition(event)
        button_entry = self.registry_for(DeviceRole.BUTTON_PAD)
        if button_entry.status is not DeviceLifecycleStatus.ACTIVE:
            return None
        if event.button_index in {0, 1, 2, 3} and not self._servotronic_usable:
            return self._transition(ButtonCommandFailed(event.button_index, event.observed_at))
        return self._transition(event, origin_button_index=event.button_index)

    def _transition(
        self,
        event: ApplicationEvent,
        *,
        previous_health: RuntimeHealth | None = None,
        previous_snapshot: ApplicationSnapshot | None = None,
        previous_button_leds: object | None = None,
        extra_effects: tuple[OutputEffect, ...] = (),
        extra_topics: frozenset[StateTopic] = frozenset(),
        origin_button_index: int | None = None,
    ) -> Commit:
        prior_snapshot = self.snapshot() if previous_snapshot is None else previous_snapshot
        prior_button_leds = (
            button_led_state(self._state) if previous_button_leds is None else previous_button_leds
        )
        result = transition(
            self._state,
            event,
            self._steering_config,
            self._active_steering_curve.definition,
            self._high_beam_strobe_config,
        )
        return self._commit_application_result(
            result,
            prior_snapshot,
            prior_button_leds,
            previous_health=previous_health,
            extra_effects=extra_effects,
            extra_topics=extra_topics,
            origin_button_index=origin_button_index,
        )

    def _commit_application_result(
        self,
        result: object,
        previous_snapshot: ApplicationSnapshot,
        previous_button_leds: object,
        *,
        previous_health: RuntimeHealth | None = None,
        extra_effects: tuple[OutputEffect, ...] = (),
        extra_topics: frozenset[StateTopic] = frozenset(),
        origin_button_index: int | None = None,
    ) -> Commit:
        assert isinstance(result, Transition)
        self._state = result.state
        self._revision += 1
        committed_snapshot = self.snapshot()
        changed_topics = _changed_controller_topics(
            previous_snapshot,
            committed_snapshot,
            buttons_changed=button_led_state(self._state) != previous_button_leds,
            health_changed=(previous_health is not None and self._health != previous_health),
        )
        changed_topics |= extra_topics
        effect_requests = tuple(
            EffectRequest(effect, origin_button_index if origin_button_index is not None else None)
            for effect in (*extra_effects, *result.effects)
        )
        return Commit(
            revision=self._revision,
            snapshot=committed_snapshot,
            effects=self._gate_effects(effect_requests),
            changed_topics=frozenset(changed_topics),
            state_changed=(
                committed_snapshot != previous_snapshot
                or button_led_state(self._state) != previous_button_leds
            ),
        )

    def _commit_startup(self, now: float) -> Commit:
        self._registry = tuple(
            replace(entry, last_transition_monotonic_s=now)
            for entry in self._registry
        )
        self._revision = 1
        return Commit(
            revision=self._revision,
            snapshot=self.snapshot(),
            effects=self._gate_effects(
                tuple(
                    EffectRequest(effect)
                    for effect in initial_effects(
                        self._state,
                        self._steering_config,
                        self._active_steering_curve.definition,
                    )
                )
            ),
            changed_topics=INITIAL_KERNEL_TOPICS,
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
            effects=self._gate_effects(tuple(EffectRequest(effect) for effect in effects)),
            changed_topics=_changed_controller_topics(
                previous_snapshot,
                committed_snapshot,
                buttons_changed=False,
                health_changed=False,
            ),
            state_changed=committed_snapshot != previous_snapshot,
        )

    def _timer(self, now: float) -> Commit:
        previous_snapshot = self.snapshot()
        previous_button_leds = button_led_state(self._state)
        previous_registry = self._registry
        extra_effects: list[OutputEffect] = []
        self._registry = tuple(expire_entry(entry, now) for entry in self._registry)
        previous_servotronic = registry_entry(previous_registry, DeviceRole.SERVOTRONIC_CONTROLLER)
        current_servotronic = self.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER)
        if (
            previous_servotronic.status is DeviceLifecycleStatus.ACTIVE
            and current_servotronic.status is not DeviceLifecycleStatus.ACTIVE
        ):
            cleared = clear_maximum_assistance(self._state)
            self._state = cleared.state
            extra_effects.extend(cleared.effects)
        registry_changed = self._registry != previous_registry
        return self._transition(
            ControlTimerElapsed(now),
            previous_snapshot=previous_snapshot,
            previous_button_leds=previous_button_leds,
            extra_effects=tuple(extra_effects),
            extra_topics=(frozenset({StateTopic.DEVICES}) if registry_changed else frozenset()),
        )

    def _registry_hello(self, observation: RegistryHelloObserved) -> Commit | None:
        return self._apply_registry_transition(
            observation.role,
            transition_hello(
                self.registry_for(observation.role),
                observation,
                self._controller_session_id,
            ),
        )

    def _registry_heartbeat(self, observation: RegistryHeartbeatObserved) -> Commit | None:
        return self._apply_registry_transition(
            observation.role,
            transition_heartbeat(
                self.registry_for(observation.role),
                observation,
                self._controller_session_id,
            ),
        )

    def _apply_registry_transition(
        self,
        role: DeviceRole,
        result: object,
    ) -> Commit | None:
        from e87canbus.device_registry import RegistryTransition

        assert isinstance(result, RegistryTransition)
        previous_entry = self.registry_for(role)
        next_entry = result.entry
        if next_entry == previous_entry and result.acknowledgement is None:
            return None
        previous_snapshot = self.snapshot()
        previous_button_leds = button_led_state(self._state)
        previous_registry = self._registry
        self._registry = tuple(
            next_entry if entry.role is role else entry for entry in self._registry
        )
        effects: list[OutputEffect] = []
        if result.acknowledgement is not None:
            ids = self._router.ids
            acknowledgement_id = (
                ids.button_pad_welcome_ack
                if role is DeviceRole.BUTTON_PAD
                else ids.servotronic_controller_welcome_ack
            )
            effects.append(
                SendRegistryFrame(
                    RoutedCanFrame(
                        CanNetwork.KCAN,
                        encode_welcome_ack(result.acknowledgement, acknowledgement_id),
                    )
                )
            )
        if (
            previous_entry.status is DeviceLifecycleStatus.ACTIVE
            and next_entry.status is not DeviceLifecycleStatus.ACTIVE
            and role is DeviceRole.SERVOTRONIC_CONTROLLER
        ):
            cleared = clear_maximum_assistance(self._state)
            self._state = cleared.state
            effects.extend(cleared.effects)
        if (
            previous_entry.status is not DeviceLifecycleStatus.ACTIVE
            and next_entry.status is DeviceLifecycleStatus.ACTIVE
        ):
            if role is DeviceRole.BUTTON_PAD:
                effects.append(SetButtonLeds(button_led_state(self._state)))
            elif self._servotronic_usable:
                effects.append(
                    steering_command_for_current_state(
                        self._state,
                        self._steering_config,
                        self._active_steering_curve.definition,
                    )
                )
        changed_topics = _changed_controller_topics(
            previous_snapshot,
            self.snapshot(),
            buttons_changed=button_led_state(self._state) != previous_button_leds,
            health_changed=False,
        )
        if self._registry != previous_registry:
            changed_topics |= {StateTopic.DEVICES}
        self._revision += 1
        return Commit(
            revision=self._revision,
            snapshot=self.snapshot(),
            effects=self._gate_effects(tuple(EffectRequest(effect) for effect in effects)),
            changed_topics=frozenset(changed_topics),
            state_changed=(
                self.snapshot() != previous_snapshot or self._registry != previous_registry
            ),
        )

    @property
    def _servotronic_usable(self) -> bool:
        return (
            self._servotronic_output_available
            and self.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER).status
            is DeviceLifecycleStatus.ACTIVE
            and self.health_for_device(DeviceRole.SERVOTRONIC_CONTROLLER).fault is None
            and self._health.steering_actuator_fault is None
        )

    def health_for_device(self, role: DeviceRole) -> DeviceRuntimeHealth:
        return next(item for item in self._health.devices if item.role is role)

    def _require_servotronic_available(self) -> None:
        entry = self.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER)
        if not self._servotronic_output_available:
            raise FeatureUnavailable(
                DeviceRole.SERVOTRONIC_CONTROLLER,
                entry.status,
                "servotronic output adapter is unavailable",
            )
        if self._health.steering_actuator_fault is not None:
            raise FeatureUnavailable(
                DeviceRole.SERVOTRONIC_CONTROLLER,
                entry.status,
                "servotronic output adapter is faulted",
            )
        if self.health_for_device(DeviceRole.SERVOTRONIC_CONTROLLER).fault is not None:
            raise FeatureUnavailable(
                DeviceRole.SERVOTRONIC_CONTROLLER,
                entry.status,
                "servotronic output adapter is faulted",
            )
        if entry.status is not DeviceLifecycleStatus.ACTIVE:
            raise FeatureUnavailable(
                DeviceRole.SERVOTRONIC_CONTROLLER,
                entry.status,
                f"servotronic controller is {entry.status.value}",
            )

    def _gate_effects(self, effects: tuple[EffectRequest, ...]) -> tuple[EffectRequest, ...]:
        button_active = (
            self.registry_for(DeviceRole.BUTTON_PAD).status is DeviceLifecycleStatus.ACTIVE
        )
        return tuple(
            request
            for request in effects
            if (
                not isinstance(request.effect, SetButtonLeds)
                or button_active
            )
            and (
                not isinstance(request.effect, SetSteeringAssistance)
                or self._servotronic_usable
            )
        )


def _changed_controller_topics(
    previous: ApplicationSnapshot,
    current: ApplicationSnapshot,
    *,
    buttons_changed: bool,
    health_changed: bool,
) -> frozenset[StateTopic]:
    """Compare fixed projections without introducing string dispatch or registration."""

    changed: set[StateTopic] = set()
    if (
        current.vehicle_speed_kph != previous.vehicle_speed_kph
        or current.speed_valid != previous.speed_valid
    ):
        changed.add(StateTopic.VEHICLE)
    if current.engine != previous.engine:
        changed.add(StateTopic.ENGINE)
    if (
        current.steering_mode != previous.steering_mode
        or current.manual_assistance_level != previous.manual_assistance_level
        or current.maximum_assistance_active != previous.maximum_assistance_active
        or current.active_steering_curve != previous.active_steering_curve
        or (current.steering_curve_activation_status != previous.steering_curve_activation_status)
    ):
        changed.add(StateTopic.STEERING)
    if buttons_changed:
        changed.add(StateTopic.BUTTONS)
    if (
        current.high_beam_enabled != previous.high_beam_enabled
        or current.high_beam_strobe_active != previous.high_beam_strobe_active
        or (
            current.high_beam_strobe_cycles_remaining
            != previous.high_beam_strobe_cycles_remaining
        )
    ):
        changed.add(StateTopic.LIGHTING)
    if health_changed:
        changed.add(StateTopic.HEALTH)
    return frozenset(changed)
