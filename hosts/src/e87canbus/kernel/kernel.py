"""The single-owner coordinator kernel shared by simulated and live runners."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import assert_never

from e87canbus.config import EngineTelemetryConfig, SteeringConfig
from e87canbus.domain.buttons.commands import button_command_configuration_error
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    built_in_active_button_profile,
    validate_saved_profile_revision,
)
from e87canbus.domain.controller import (
    ApplicationSnapshot,
    execute_operator_intent,
    normalize_state,
    snapshot,
    transition,
)
from e87canbus.domain.events import ApplicationEvent, ButtonPressed, ControlTimerElapsed
from e87canbus.domain.intents import OperatorIntent
from e87canbus.domain.state import ApplicationState
from e87canbus.domain.steering.curves import (
    ActiveSteeringCurve,
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
from e87canbus.kernel.health import RuntimeFault, RuntimeFaultKind, RuntimeHealth
from e87canbus.kernel.inputs import (
    ActivateButtonProfile,
    ActivateSteeringCurve,
    CanReaderFailed,
    ControllerInput,
    ExecuteOperatorIntent,
    InboxOverflowed,
    KernelStarted,
    ReceivedCanFrame,
    ShutdownRequested,
    TimerElapsed,
)
from e87canbus.protocol.can import RoutedCanFrame

LOGGER = logging.getLogger(__name__)


class CoordinatorKernel:
    """Decode and commit one explicitly timed input at a time."""

    def __init__(
        self,
        state: ApplicationState | None = None,
        steering_config: SteeringConfig | None = None,
        engine_telemetry_config: EngineTelemetryConfig | None = None,
        decoder: Callable[[RoutedCanFrame, float], ApplicationEvent | None] | None = None,
        active_steering_curve: ActiveSteeringCurve | None = None,
        button_profile: ActiveButtonProfile | None = None,
    ) -> None:
        self._steering_config = steering_config or SteeringConfig()
        self._engine_telemetry_config = engine_telemetry_config or EngineTelemetryConfig()
        self._state = normalize_state(state or ApplicationState(), self._steering_config)
        self._decoder = decoder
        self._active_steering_curve = active_steering_curve or initial_active_steering_curve()
        validate_active_steering_curve(self._active_steering_curve)
        self._button_profile = button_profile or built_in_active_button_profile()
        self._button_profile_saved_revision: int | None = None
        self._lifecycle = KernelLifecycle.CREATED
        self._health = RuntimeHealth()

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def health(self) -> RuntimeHealth:
        return self._health

    @property
    def button_profile(self) -> ActiveButtonProfile:
        return self._button_profile

    def snapshot(self) -> ApplicationSnapshot:
        return snapshot(
            self._state,
            self._steering_config,
            self._engine_telemetry_config,
            self._active_steering_curve,
            self._button_profile.profile_id,
            self._button_profile_saved_revision,
        )

    def configure_initial_steering_curve(self, curve: ActiveSteeringCurve) -> None:
        if self._lifecycle is not KernelLifecycle.CREATED:
            raise RuntimeError("initial steering curve must be configured before startup")
        validate_active_steering_curve(curve)
        self._active_steering_curve = curve

    def configure_initial_button_profile(
        self, profile: ActiveButtonProfile, saved_profile_revision: int | None = None
    ) -> None:
        if self._lifecycle is not KernelLifecycle.CREATED:
            raise RuntimeError("initial button profile must be configured before startup")
        if not isinstance(profile, ActiveButtonProfile):
            raise TypeError("profile must be an ActiveButtonProfile")
        validate_saved_profile_revision(saved_profile_revision)
        self._button_profile = profile
        self._button_profile_saved_revision = saved_profile_revision

    def diagnostics(self) -> DiagnosticSnapshot:
        return DiagnosticSnapshot(self._lifecycle, self._health)

    def dispatch(self, kernel_input: ControllerInput) -> Commit | None:
        if self._lifecycle is KernelLifecycle.STOPPED:
            return None
        match kernel_input:
            case KernelStarted():
                if self._lifecycle is not KernelLifecycle.CREATED:
                    return None
                self._lifecycle = KernelLifecycle.RUNNING
                return Commit(self.snapshot(), INITIAL_KERNEL_TOPICS)
            case ShutdownRequested():
                self._lifecycle = KernelLifecycle.STOPPED
                return None
            case CanReaderFailed(network, failed_at, message):
                previous = self._health
                self._health = self._health.with_fault(
                    network, RuntimeFault(RuntimeFaultKind.CAN_READER, failed_at, message)
                )
                return self._commit_health(previous)
            case InboxOverflowed(network, failed_at, message):
                previous = self._health
                self._health = self._health.with_inbox_overflow(
                    network, RuntimeFault(RuntimeFaultKind.INBOX_OVERFLOW, failed_at, message)
                )
                return self._commit_health(previous)
            case ReceivedCanFrame():
                return (
                    self._receive(kernel_input)
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case TimerElapsed(now):
                return (
                    self._transition(ControlTimerElapsed(now))
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case ActivateSteeringCurve():
                return (
                    self._activate_steering_curve(kernel_input)
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case ActivateButtonProfile():
                return (
                    self._activate_button_profile(kernel_input)
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case ButtonPressed():
                return (
                    self._dispatch_button_press(kernel_input)
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case ExecuteOperatorIntent():
                return (
                    self._dispatch_operator_intent(kernel_input.intent)
                    if self._lifecycle is KernelLifecycle.RUNNING
                    else None
                )
            case _:
                assert_never(kernel_input)

    def _receive(self, received: ReceivedCanFrame) -> Commit | None:
        routed = RoutedCanFrame(received.network, received.frame)
        try:
            event = None if self._decoder is None else self._decoder(routed, received.received_at)
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

    def _dispatch_button_press(self, event: ButtonPressed) -> Commit | None:
        intent = self._button_profile.intent_for_press(event.button_index)
        if intent is None:
            return None
        unusable = button_command_configuration_error(intent, self._steering_config)
        if unusable is not None:
            LOGGER.warning(
                "ignored button press with rejected command: button=%d profile=%s error=%s",
                event.button_index,
                self._button_profile.profile_id,
                unusable,
            )
            return None
        return self._dispatch_operator_intent(intent)

    def _dispatch_operator_intent(self, intent: OperatorIntent) -> Commit:
        previous = self.snapshot()
        result = execute_operator_intent(self._state, intent, self._steering_config)
        return self._commit_application_result(result, previous)

    def _transition(self, event: ApplicationEvent) -> Commit:
        previous = self.snapshot()
        return self._commit_application_result(transition(self._state, event), previous)

    def _commit_application_result(
        self, result: ApplicationState, previous: ApplicationSnapshot
    ) -> Commit:
        self._state = result
        current = self.snapshot()
        return Commit(
            current,
            changed_controller_topics(previous, current, health_changed=False),
        )

    def _commit_health(self, previous: RuntimeHealth) -> Commit:
        topics = frozenset({StateTopic.HEALTH}) if self._health != previous else frozenset()
        return Commit(self.snapshot(), topics)

    def _activate_steering_curve(self, request: ActivateSteeringCurve) -> Commit:
        validate_steering_curve_definition(request.definition)
        current = self._active_steering_curve
        fingerprint = steering_curve_fingerprint(request.definition)
        previous = self.snapshot()
        self._active_steering_curve = ActiveSteeringCurve(
            definition=request.definition,
            fingerprint=fingerprint,
            activation_revision=current.activation_revision + (fingerprint != current.fingerprint),
            saved_profile_id=request.saved_profile_id,
            saved_profile_revision=request.saved_profile_revision,
        )
        committed = self.snapshot()
        return Commit(
            committed,
            changed_controller_topics(previous, committed, health_changed=False),
        )

    def _activate_button_profile(self, request: ActivateButtonProfile) -> Commit:
        previous = self.snapshot()
        self._button_profile = request.profile
        self._button_profile_saved_revision = request.saved_profile_revision
        committed = self.snapshot()
        return Commit(
            committed,
            changed_controller_topics(previous, committed, health_changed=False),
        )
