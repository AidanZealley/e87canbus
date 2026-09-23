"""The single-owner coordinator kernel shared by simulated and live runners."""

from __future__ import annotations

import logging
import secrets
from dataclasses import replace
from typing import assert_never

from e87canbus.adapters.output import EffectRequest, OutputEffect, SendRegistryFrame
from e87canbus.config import (
    EngineTelemetryConfig,
    SteeringConfig,
)
from e87canbus.domain.buttons.commands import button_command_configuration_error
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    built_in_active_button_profile,
    validate_saved_profile_revision,
)
from e87canbus.domain.controller import (
    ApplicationSnapshot,
    Transition,
    clear_maximum_assistance,
    execute_operator_intent,
    initial_effects,
    normalize_state,
    snapshot,
    steering_command_for_active_curve,
    steering_command_for_current_state,
    transition,
)
from e87canbus.domain.devices.catalogue import DeviceLifecycleStatus, DeviceRole, DeviceSource
from e87canbus.domain.devices.registry import (
    DeviceRegistryEntry,
    FeatureUnavailable,
    RegistryHeartbeatObserved,
    RegistryHelloObserved,
    RegistryTransition,
    expire_entry,
    initial_registry,
    registry_entry,
    transition_heartbeat,
    transition_hello,
)
from e87canbus.domain.events import (
    ApplicationEffect,
    ApplicationEvent,
    ButtonPressed,
    ConfigureServotronicCurve,
    ControlTimerElapsed,
    SetSteeringAssistance,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.domain.intents import (
    OperatorIntent,
    intent_requires_servotronic,
)
from e87canbus.domain.state import ApplicationState
from e87canbus.domain.steering.curves import (
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    initial_active_steering_curve,
    steering_curve_fingerprint,
    validate_active_steering_curve,
    validate_steering_curve_definition,
)
from e87canbus.kernel.commit import (
    INITIAL_KERNEL_TOPICS,
    Commit,
    DiagnosticSnapshot,
    KernelLifecycle,
    StateTopic,
    changed_controller_topics,
)
from e87canbus.kernel.health import (
    DeviceRuntimeHealth,
    RuntimeFault,
    RuntimeFaultKind,
    RuntimeHealth,
)
from e87canbus.kernel.inputs import (
    ActivateButtonProfile,
    ActivateSteeringCurve,
    CanEffectExecutionFailed,
    CanReaderFailed,
    ControllerInput,
    DeviceAdapterFailed,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ServotronicStatusObserved,
    ShutdownRequested,
    SteeringActuatorFailed,
    TimerElapsed,
)
from e87canbus.protocol.can import RoutedCanFrame
from e87canbus.protocol.router import ProtocolRouter
from e87canbus.protocol.servotronic_protocol import CurveResult, ServotronicStatus, pack_curve

LOGGER = logging.getLogger(__name__)

_controller_session_seed = secrets.randbelow(0xFFFF) + 1


def _new_controller_session_id() -> int:
    global _controller_session_seed
    session_id = _controller_session_seed
    _controller_session_seed = (_controller_session_seed % 0xFFFF) + 1
    return session_id


class CoordinatorKernel:
    """Decode and commit one explicitly timed input at a time."""

    def __init__(
        self,
        state: ApplicationState | None = None,
        steering_config: SteeringConfig | None = None,
        engine_telemetry_config: EngineTelemetryConfig | None = None,
        router: ProtocolRouter | None = None,
        active_steering_curve: ActiveSteeringCurve | None = None,
        device_sources: dict[DeviceRole, DeviceSource] | None = None,
        servotronic_output_available: bool = True,
        servotronic_config_available: bool = False,
        button_profile: ActiveButtonProfile | None = None,
    ) -> None:
        self._steering_config = steering_config or SteeringConfig()
        self._engine_telemetry_config = engine_telemetry_config or EngineTelemetryConfig()
        self._button_profile = button_profile or built_in_active_button_profile()
        self._button_profile_saved_revision: int | None = None
        self._state = normalize_state(
            state or ApplicationState(),
            self._steering_config,
        )
        self._router = router or ProtocolRouter()
        self._controller_session_id = _new_controller_session_id()
        self._registry = initial_registry(device_sources)
        self._servotronic_output_available = servotronic_output_available
        self._servotronic_config_available = servotronic_config_available
        self._active_steering_curve = active_steering_curve or initial_active_steering_curve()
        validate_active_steering_curve(self._active_steering_curve)
        self._steering_curve_activation_status = SteeringCurveActivationStatus.ACTIVE
        self._servotronic_reported_status: ServotronicStatus | None = None
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
    def servotronic_status(self) -> ServotronicStatus | None:
        """The last observed controller status, retained only while it stays active.

        Adapters read this for the live projection instead of caching their own copy; it is
        reset in one place when the controller deactivates or its session changes, so the
        projection stops serving stale telemetry.
        """

        return self._servotronic_reported_status

    @property
    def registry(self) -> tuple[DeviceRegistryEntry, ...]:
        return self._registry

    @property
    def button_profile(self) -> ActiveButtonProfile:
        return self._button_profile

    @property
    def button_profile_saved_revision(self) -> int | None:
        return self._button_profile_saved_revision

    def registry_for(self, role: DeviceRole) -> DeviceRegistryEntry:
        return registry_entry(self._registry, role)

    def next_deadline(self) -> float | None:
        deadlines = [
            entry.next_deadline for entry in self._registry if entry.next_deadline is not None
        ]
        return min(deadlines) if deadlines else None

    def snapshot(self) -> ApplicationSnapshot:
        return snapshot(
            self._state,
            self._steering_config,
            self._engine_telemetry_config,
            self._active_steering_curve,
            self._steering_curve_activation_status,
            self._button_profile.profile_id,
            self._button_profile_saved_revision,
            # ``curve_activation_available`` gates curve ACTIVATION in the UI.
            self._servotronic_config_available or self._servotronic_output_available,
        )

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        """Install persisted state before the kernel begins processing inputs."""

        if self._lifecycle is not KernelLifecycle.CREATED or self._revision != 0:
            raise RuntimeError("initial steering curve must be configured before startup")
        validate_active_steering_curve(curve)
        self._active_steering_curve = curve

    def configure_initial_button_profile(
        self,
        profile: ActiveButtonProfile,
        saved_profile_revision: int | None = None,
    ) -> None:
        """Install a persisted button profile before the kernel starts."""

        if self._lifecycle is not KernelLifecycle.CREATED or self._revision != 0:
            raise RuntimeError("initial button profile must be configured before startup")
        if not isinstance(profile, ActiveButtonProfile):
            raise TypeError("profile must be a ActiveButtonProfile")
        validate_saved_profile_revision(saved_profile_revision)
        self._button_profile = profile
        self._button_profile_saved_revision = saved_profile_revision

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
                    return self._commit_health(previous_health)
                previous_snapshot = self.snapshot()
                cleared_effects = self._deactivate_servotronic()
                return self._commit_application_result(
                    Transition(self._state, cleared_effects),
                    previous_snapshot,
                    previous_health=previous_health,
                )
            case CanEffectExecutionFailed(network, failed_at, message):
                previous_health = self._health
                self._health = self._health.with_fault(
                    network,
                    RuntimeFault(
                        RuntimeFaultKind.CAN_EFFECT_EXECUTION,
                        failed_at,
                        message,
                    ),
                )
                return self._commit_health(previous_health)
            case SteeringActuatorFailed(failed_at, message):
                previous_health = self._health
                self._health = self._health.with_steering_actuator_fault(
                    RuntimeFault(
                        RuntimeFaultKind.STEERING_ACTUATOR,
                        failed_at,
                        message,
                    )
                )
                if self._lifecycle is KernelLifecycle.STOPPED:
                    return self._commit_health(previous_health)
                previous_snapshot = self.snapshot()
                cleared_effects = self._deactivate_servotronic()
                return self._commit_application_result(
                    Transition(self._state, cleared_effects),
                    previous_snapshot,
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
            case ActivateSteeringCurve():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                self._require_servotronic(for_curve_config=True)
                return self._activate_steering_curve(kernel_input)
            case ActivateButtonProfile():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._activate_button_profile(kernel_input)
            case ServotronicStatusObserved():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._servotronic_status(kernel_input.status)
            case ButtonPressed():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                return self._dispatch_button_press(kernel_input)
            case ExecuteOperatorIntent():
                if self._lifecycle is not KernelLifecycle.RUNNING:
                    return None
                if intent_requires_servotronic(kernel_input.intent):
                    self._require_servotronic()
                return self._dispatch_operator_intent(kernel_input.intent)
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
        return self._transition(event)

    def _dispatch_button_press(self, event: ButtonPressed) -> Commit | None:
        intent = self._button_profile.intent_for_press(event.button_index)
        if intent is None:
            return None
        unusable = button_command_configuration_error(intent, self._steering_config)
        if unusable is not None:
            LOGGER.warning(
                "ignored button press whose command the configuration rejects: "
                "button=%d profile=%s error=%s",
                event.button_index,
                self._button_profile.profile_id,
                unusable,
            )
            return None
        if intent_requires_servotronic(intent):
            self._require_servotronic()
        return self._dispatch_operator_intent(intent)

    def _execute_operator_intent(
        self,
        intent: OperatorIntent,
    ) -> Transition:
        return execute_operator_intent(
            self._state,
            intent,
            self._steering_config,
            active_definition=self._active_steering_curve.definition,
        )

    def _dispatch_operator_intent(
        self,
        intent: OperatorIntent,
    ) -> Commit:
        """Execute a non-button adapter request through the canonical intent path."""

        previous_snapshot = self.snapshot()
        result = self._execute_operator_intent(intent)
        return self._commit_application_result(
            result,
            previous_snapshot,
        )

    def _transition(
        self,
        event: ApplicationEvent,
        *,
        previous_health: RuntimeHealth | None = None,
        previous_snapshot: ApplicationSnapshot | None = None,
        extra_effects: tuple[OutputEffect, ...] = (),
        extra_topics: frozenset[StateTopic] = frozenset(),
    ) -> Commit:
        prior_snapshot = self.snapshot() if previous_snapshot is None else previous_snapshot
        result = transition(
            self._state,
            event,
            self._steering_config,
            self._active_steering_curve.definition,
        )
        return self._commit_application_result(
            result,
            prior_snapshot,
            previous_health=previous_health,
            extra_effects=extra_effects,
            extra_topics=extra_topics,
        )

    def _commit_application_result(
        self,
        result: Transition,
        previous_snapshot: ApplicationSnapshot,
        *,
        previous_health: RuntimeHealth | None = None,
        extra_effects: tuple[OutputEffect, ...] = (),
        extra_topics: frozenset[StateTopic] = frozenset(),
    ) -> Commit:
        self._state = result.state
        self._revision += 1
        committed_snapshot = self.snapshot()
        changed_topics = changed_controller_topics(
            previous_snapshot,
            committed_snapshot,
            health_changed=(previous_health is not None and self._health != previous_health),
        )
        changed_topics |= extra_topics
        effect_requests = tuple(
            EffectRequest(
                effect,
            )
            for effect in (*extra_effects, *result.effects)
        )
        return Commit(
            revision=self._revision,
            snapshot=committed_snapshot,
            effects=self._gate_effects(effect_requests),
            changed_topics=frozenset(changed_topics),
            state_changed=committed_snapshot != previous_snapshot,
        )

    def _commit_health(self, previous_health: RuntimeHealth) -> Commit:
        """Commit an accepted diagnostic-only input through the kernel contract."""

        self._revision += 1
        return Commit(
            revision=self._revision,
            snapshot=self.snapshot(),
            effects=(),
            changed_topics=(
                frozenset({StateTopic.HEALTH}) if self._health != previous_health else frozenset()
            ),
            state_changed=False,
        )

    def _commit_startup(self, now: float) -> Commit:
        self._registry = tuple(
            replace(entry, last_transition_monotonic_s=now) for entry in self._registry
        )
        self._revision = 1
        startup_effects = initial_effects(
            self._state,
            self._steering_config,
            self._active_steering_curve.definition,
        )
        return Commit(
            revision=self._revision,
            snapshot=self.snapshot(),
            effects=self._gate_effects(tuple(EffectRequest(effect) for effect in startup_effects)),
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
        self._steering_curve_activation_status = (
            SteeringCurveActivationStatus.ACTIVATING
            if self._servotronic_config_available
            else SteeringCurveActivationStatus.ACTIVE
        )
        self._revision += 1
        effects: tuple[ApplicationEffect, ...] = ()
        if self._servotronic_config_available:
            effects = (
                ConfigureServotronicCurve(request.definition, next_active.activation_revision),
            )
        if definition_changed:
            command = steering_command_for_active_curve(
                self._state,
                self._steering_config,
                request.definition,
            )
            if command is not None:
                effects = (*effects, command)
        committed_snapshot = self.snapshot()
        return Commit(
            revision=self._revision,
            snapshot=committed_snapshot,
            effects=self._gate_effects(tuple(EffectRequest(effect) for effect in effects)),
            changed_topics=changed_controller_topics(
                previous_snapshot,
                committed_snapshot,
                health_changed=False,
            ),
            state_changed=committed_snapshot != previous_snapshot,
        )

    def _activate_button_profile(self, request: ActivateButtonProfile) -> Commit:
        """Replace active routing and publish the selected profile identity."""

        previous = self.snapshot()
        self._button_profile = request.profile
        self._button_profile_saved_revision = request.saved_profile_revision
        self._revision += 1
        committed = self.snapshot()
        return Commit(
            revision=self._revision,
            snapshot=committed,
            effects=(),
            changed_topics=changed_controller_topics(previous, committed, health_changed=False),
            state_changed=committed != previous,
        )

    def _servotronic_status(self, status: ServotronicStatus) -> Commit:
        previous_snapshot = self.snapshot()
        self._servotronic_reported_status = status
        matches = self._servotronic_curve_matches(status)
        self._steering_curve_activation_status = (
            SteeringCurveActivationStatus.ACTIVE
            if matches
            else SteeringCurveActivationStatus.ACTIVATION_FAILED
            if status.result is not CurveResult.ACCEPTED
            else SteeringCurveActivationStatus.ACTIVATING
        )
        self._revision += 1
        committed = self.snapshot()
        return Commit(
            self._revision,
            committed,
            (),
            changed_controller_topics(previous_snapshot, committed, health_changed=False)
            | {StateTopic.STEERING},
            committed != previous_snapshot,
        )

    def _servotronic_curve_matches(self, status: ServotronicStatus | None) -> bool:
        if status is None or status.result is not CurveResult.ACCEPTED:
            return False
        expected = pack_curve(
            self._active_steering_curve.definition,
            self._active_steering_curve.activation_revision,
        )
        return (
            status.activation_revision == self._active_steering_curve.activation_revision
            and status.curve_crc32 == int.from_bytes(expected[-4:], "little")
        )

    def _deactivate_servotronic(self) -> tuple[ApplicationEffect, ...]:
        """Drop retained telemetry and the maximum-assist override on controller loss.

        Shared by every path where the Servotronic controller goes active->inactive (adapter
        fault, actuator fault, heartbeat expiry, registry transition), keeping the kernel-owned
        status reset in exactly one place.
        """

        self._servotronic_reported_status = None
        cleared = clear_maximum_assistance(self._state)
        self._state = cleared.state
        return cleared.effects

    def _timer(self, now: float) -> Commit:
        previous_snapshot = self.snapshot()
        previous_registry = self._registry
        extra_effects: list[OutputEffect] = []
        self._registry = tuple(expire_entry(entry, now) for entry in self._registry)
        previous_servotronic = registry_entry(previous_registry, DeviceRole.SERVOTRONIC_CONTROLLER)
        current_servotronic = self.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER)
        if (
            previous_servotronic.status is DeviceLifecycleStatus.ACTIVE
            and current_servotronic.status is not DeviceLifecycleStatus.ACTIVE
        ):
            extra_effects.extend(self._deactivate_servotronic())
        registry_changed = self._registry != previous_registry
        return self._transition(
            ControlTimerElapsed(now),
            previous_snapshot=previous_snapshot,
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
        result: RegistryTransition,
    ) -> Commit | None:
        previous_entry = self.registry_for(role)
        next_entry = result.entry
        if next_entry == previous_entry and result.acknowledgement is None:
            return None
        previous_snapshot = self.snapshot()
        previous_registry = self._registry
        self._registry = tuple(
            next_entry if entry.role is role else entry for entry in self._registry
        )
        servotronic_deactivated = (
            role is DeviceRole.SERVOTRONIC_CONTROLLER
            and previous_entry.status is DeviceLifecycleStatus.ACTIVE
            and next_entry.status is not DeviceLifecycleStatus.ACTIVE
        )
        effects: list[OutputEffect] = []
        if result.acknowledgement is not None:
            effects.append(
                SendRegistryFrame(self._router.encode_registry_ack(role, result.acknowledgement))
            )
        if servotronic_deactivated:
            effects.extend(self._deactivate_servotronic())
        elif (
            role is DeviceRole.SERVOTRONIC_CONTROLLER
            and next_entry.device_session_id != previous_entry.device_session_id
        ):
            # A new controller identity invalidates retained telemetry even without a lifecycle
            # transition; the active->inactive path already drops it via _deactivate_servotronic.
            self._servotronic_reported_status = None
        if (
            previous_entry.status is not DeviceLifecycleStatus.ACTIVE
            and next_entry.status is DeviceLifecycleStatus.ACTIVE
        ):
            if self._servotronic_usable:
                effects.append(
                    steering_command_for_current_state(
                        self._state,
                        self._steering_config,
                        self._active_steering_curve.definition,
                    )
                )
            elif (
                role is DeviceRole.SERVOTRONIC_CONTROLLER
                and self._servotronic_config_available
                and not self._servotronic_curve_matches(self._servotronic_reported_status)
            ):
                self._steering_curve_activation_status = SteeringCurveActivationStatus.ACTIVATING
                effects.append(
                    ConfigureServotronicCurve(
                        self._active_steering_curve.definition,
                        self._active_steering_curve.activation_revision,
                    )
                )
        changed_topics = changed_controller_topics(
            previous_snapshot,
            self.snapshot(),
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

    def _require_servotronic(self, *, for_curve_config: bool = False) -> None:
        """Assert the controller can serve the requested capability.

        Curve activation only needs the coordinator's config path when it is available; every
        other request (and curve activation when config is unavailable) also needs the output
        adapter to be present and unfaulted.
        """

        entry = self.registry_for(DeviceRole.SERVOTRONIC_CONTROLLER)
        if not (for_curve_config and self._servotronic_config_available):
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
        return tuple(
            request
            for request in effects
            if not isinstance(request.effect, SetSteeringAssistance) or self._servotronic_usable
        )
