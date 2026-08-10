"""The event reducer: one observed/timer/failure event to its next state.

``transition`` is the pure reducer for everything that is not an operator intent
(speed and engine samples, control ticks, high-beam strobe advances, fallbacks
and button-feedback deadlines). ``Transition`` is the shared result type used by
both this reducer and the intent path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.config import HighBeamStrobeConfig, SteeringConfig
from e87canbus.domain.controller.steering import steering_command
from e87canbus.domain.events import (
    ApplicationEffect,
    ApplicationEvent,
    ButtonCommandFailed,
    ButtonFeedbackDeadlineReached,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    HighBeamStrobeDeadlineReached,
    OilTemperatureObserved,
    SetHighBeam,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
    TriggerButtonPadBlink,
    button_feedback_duration_s,
)
from e87canbus.domain.state import ApplicationState, MaximumAssistance, SteeringMode
from e87canbus.domain.steering.curves import SteeringCurveDefinition, clamp_manual_level


@dataclass(frozen=True)
class Transition:
    state: ApplicationState
    effects: tuple[ApplicationEffect, ...] = ()


def transition(
    state: ApplicationState,
    event: ApplicationEvent,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
    high_beam_strobe_config: HighBeamStrobeConfig | None = None,
) -> Transition:
    """Return the complete next state and ordered effects for one event."""

    match event:
        case HighBeamStrobeDeadlineReached(now):
            return _advance_high_beam_strobe(
                state,
                now,
                high_beam_strobe_config or HighBeamStrobeConfig(),
            )
        case SpeedObserved(sample):
            next_state = replace(
                state,
                speed_sample=replace(sample, speed_kph=max(0.0, sample.speed_kph)),
                speed_evaluated_at=max(state.speed_evaluated_at, sample.observed_at),
            )
            # Starting the virtual car publishes an explicit 0 km/h sample.  Apply
            # Auto's curve result immediately so the live marker never renders the
            # prior zero-assist fallback while waiting for the next control tick.
            if (
                not isinstance(next_state.steering, MaximumAssistance)
                and next_state.steering.mode is SteeringMode.AUTO
                and sample.speed_kph == 0.0
            ):
                return Transition(
                    next_state,
                    (steering_command(next_state, config, active_definition),),
                )
            return Transition(next_state)
        case EngineRpmObserved(sample):
            return Transition(replace(state, engine_rpm_sample=sample))
        case OilTemperatureObserved(sample):
            return Transition(replace(state, oil_temperature_sample=sample))
        case CoolantTemperatureObserved(sample):
            return Transition(replace(state, coolant_temperature_sample=sample))
        case ControlTimerElapsed(now):
            next_state = replace(
                state,
                speed_evaluated_at=max(state.speed_evaluated_at, now),
                engine_telemetry_evaluated_at=max(
                    state.engine_telemetry_evaluated_at,
                    now,
                ),
            )
            return Transition(
                next_state,
                (steering_command(next_state, config, active_definition),),
            )
        case SteeringFallbackRequested(reason):
            return Transition(
                state,
                (
                    SetSteeringAssistance(
                        0.0,
                        _fallback_command_reason(reason),
                    ),
                ),
            )
        case ButtonCommandFailed(button_index, occurred_at, feedback):
            deadlines: list[float | None] = list(state.button_feedback_deadlines)
            pending = list(state.button_feedback)
            deadlines[button_index] = occurred_at + button_feedback_duration_s(feedback.pulses)
            pending[button_index] = feedback
            next_state = replace(
                state,
                button_feedback_deadlines=tuple(deadlines),
                button_feedback=tuple(pending),
            )
            return Transition(next_state, (TriggerButtonPadBlink(button_index, feedback),))
        case ButtonFeedbackDeadlineReached(now):
            next_deadlines: tuple[float | None, ...] = tuple(
                None if deadline is not None and deadline <= now else deadline
                for deadline in state.button_feedback_deadlines
            )
            if next_deadlines == state.button_feedback_deadlines:
                return Transition(state)
            next_feedback = tuple(
                None if deadline is not None and deadline <= now else feedback
                for deadline, feedback in zip(
                    state.button_feedback_deadlines,
                    state.button_feedback,
                    strict=True,
                )
            )
            next_state = replace(
                state,
                button_feedback_deadlines=next_deadlines,
                button_feedback=next_feedback,
            )
            # Blink tracks carry final_rgb and stop themselves. Publishing the
            # cleared state is sufficient; transmitting a cleanup scene can
            # overwrite a blink that is still queued in the ISO-TP transport.
            return Transition(next_state)
        case _:
            assert_never(event)


def normalize_state(state: ApplicationState, config: SteeringConfig) -> ApplicationState:
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    normal = replace(
        normal,
        manual_level=clamp_manual_level(normal.manual_level, config.manual_level_count),
    )
    return replace(
        state,
        steering=(
            MaximumAssistance(previous=normal)
            if isinstance(steering, MaximumAssistance)
            else normal
        ),
    )


def _advance_high_beam_strobe(
    state: ApplicationState,
    now: float,
    config: HighBeamStrobeConfig,
) -> Transition:
    deadline = state.high_beam_next_transition_at
    if deadline is None or now < deadline:
        return Transition(state)
    if state.high_beam_enabled:
        next_state = replace(
            state,
            high_beam_enabled=False,
            high_beam_next_transition_at=now + config.deasserted_duration_s,
        )
        return Transition(next_state, (SetHighBeam(False),))

    remaining = state.high_beam_strobe_cycles_remaining - 1
    if remaining == 0:
        return Transition(
            replace(
                state,
                high_beam_strobe_cycles_remaining=0,
                high_beam_next_transition_at=None,
            )
        )
    next_state = replace(
        state,
        high_beam_enabled=True,
        high_beam_strobe_cycles_remaining=remaining,
        high_beam_next_transition_at=now + config.asserted_duration_s,
    )
    return Transition(next_state, (SetHighBeam(True),))


def _fallback_command_reason(
    reason: SteeringFallbackReason,
) -> SteeringCommandReason:
    match reason:
        case SteeringFallbackReason.CAN_READER_FAILURE:
            return SteeringCommandReason.CAN_READER_FAILURE
        case SteeringFallbackReason.INBOX_OVERFLOW:
            return SteeringCommandReason.INBOX_OVERFLOW
        case SteeringFallbackReason.SHUTDOWN:
            return SteeringCommandReason.SHUTDOWN
        case _:
            assert_never(reason)
