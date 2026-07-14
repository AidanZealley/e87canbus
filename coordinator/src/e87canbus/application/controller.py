"""Pure hardware-independent application decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.application.events import (
    BUTTON_LED_COUNT,
    ApplicationEffect,
    ApplicationEvent,
    ButtonLedState,
    ButtonPressed,
    ControlTimerElapsed,
    LedColour,
    SetButtonLeds,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    SteeringMode,
)
from e87canbus.config import SteeringConfig
from e87canbus.features.steering import (
    ActiveSteeringCurve,
    CurveInterpolation,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    clamp_manual_level,
    interpolate_steering_curve_definition,
)

STEERING_MODE_BUTTON_INDEX = 0
MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    maximum_assistance_active: bool
    speed_valid: bool
    active_steering_curve: ActiveSteeringCurve
    steering_curve_activation_status: SteeringCurveActivationStatus
    supported_steering_curve_interpolations: tuple[CurveInterpolation, ...] = (
        CurveInterpolation.LINEAR_V1,
        CurveInterpolation.MONOTONE_CUBIC_V1,
    )


@dataclass(frozen=True)
class Transition:
    state: ApplicationState
    effects: tuple[ApplicationEffect, ...] = ()


def transition(
    state: ApplicationState,
    event: ApplicationEvent,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> Transition:
    """Return the complete next state and ordered effects for one event."""

    match event:
        case SpeedObserved(sample):
            return Transition(
                replace(
                    state,
                    speed_sample=replace(sample, speed_kph=max(0.0, sample.speed_kph)),
                    speed_evaluated_at=max(state.speed_evaluated_at, sample.observed_at),
                )
            )
        case ControlTimerElapsed(now):
            next_state = replace(
                state,
                speed_evaluated_at=max(state.speed_evaluated_at, now),
            )
            return Transition(
                next_state,
                (_steering_command(next_state, config, active_definition),),
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
        case ButtonPressed(button_index):
            new_state = _button_transition(state, button_index, config)
            previous_leds = button_led_state(state)
            new_leds = button_led_state(new_state)
            effects: tuple[ApplicationEffect, ...] = (
                () if new_leds == previous_leds else (SetButtonLeds(new_leds),)
            )
            return Transition(new_state, effects)
        case _:
            assert_never(event)


def snapshot(
    state: ApplicationState,
    config: SteeringConfig,
    active_curve: ActiveSteeringCurve,
    activation_status: SteeringCurveActivationStatus,
    supported_interpolations: tuple[CurveInterpolation, ...] = (
        CurveInterpolation.LINEAR_V1,
        CurveInterpolation.MONOTONE_CUBIC_V1,
    ),
) -> ApplicationSnapshot:
    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
        maximum_assistance_active=maximum_active,
        speed_valid=_speed_is_valid(state, config),
        active_steering_curve=active_curve,
        steering_curve_activation_status=activation_status,
        supported_steering_curve_interpolations=supported_interpolations,
    )


def initial_effects(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> tuple[ApplicationEffect, ...]:
    """Return the complete output projection for synchronization."""

    return (
        SetButtonLeds(button_led_state(state)),
        _steering_command(state, config, active_definition),
    )


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


def _button_transition(
    state: ApplicationState,
    button_index: int,
    config: SteeringConfig,
) -> ApplicationState:
    match button_index:
        case 0:
            return _toggle_steering_mode(state)
        case 1:
            return _adjust_assistance(state, -1, config)
        case 2:
            return _adjust_assistance(state, 1, config)
        case 3:
            return _toggle_maximum_assistance(state)
        case _:
            return state


def _toggle_steering_mode(state: ApplicationState) -> ApplicationState:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return replace(
            state,
            steering=replace(steering.previous, mode=SteeringMode.AUTO),
        )
    mode = SteeringMode.MANUAL if steering.mode is SteeringMode.AUTO else SteeringMode.AUTO
    new_state = replace(state, steering=replace(steering, mode=mode))
    return new_state


def _adjust_assistance(
    state: ApplicationState,
    delta: int,
    config: SteeringConfig,
) -> ApplicationState:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        new_state = replace(
            state,
            steering=replace(steering.previous, mode=SteeringMode.MANUAL),
        )
        return new_state
    if steering.mode is SteeringMode.AUTO:
        new_state = replace(state, steering=replace(steering, mode=SteeringMode.MANUAL))
        return new_state

    manual_level = clamp_manual_level(
        steering.manual_level + delta,
        config.manual_level_count,
    )
    return replace(state, steering=replace(steering, manual_level=manual_level))


def _toggle_maximum_assistance(
    state: ApplicationState,
) -> ApplicationState:
    steering = state.steering
    new_state = replace(
        state,
        steering=(
            steering.previous
            if isinstance(steering, MaximumAssistance)
            else MaximumAssistance(previous=steering)
        ),
    )
    return new_state


def _steering_projection(
    state: ApplicationState,
    config: SteeringConfig,
) -> tuple[SteeringMode, int, bool]:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SteeringMode.MANUAL, config.manual_level_count - 1, True
    return steering.mode, steering.manual_level, False


def button_led_state(state: ApplicationState) -> ButtonLedState:
    """Derive the complete button-pad LED projection from application state."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    mode_colour = LedColour.BLUE if mode is SteeringMode.AUTO else LedColour.AMBER
    maximum_colour = (
        LedColour.WHITE if isinstance(state.steering, MaximumAssistance) else LedColour.OFF
    )
    return ButtonLedState(
        tuple(
            mode_colour
            if index == STEERING_MODE_BUTTON_INDEX
            else maximum_colour
            if index == MAXIMUM_ASSISTANCE_BUTTON_INDEX
            else LedColour.OFF
            for index in range(BUTTON_LED_COUNT)
        )
    )


def _steering_command(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM)
    if steering.mode is SteeringMode.MANUAL:
        denominator = max(config.manual_level_count - 1, 1)
        return SetSteeringAssistance(
            steering.manual_level / denominator,
            SteeringCommandReason.MANUAL,
        )
    sample = state.speed_sample
    if sample is None:
        return SetSteeringAssistance(
            0.0,
            SteeringCommandReason.SPEED_NEVER_OBSERVED,
        )
    if not _speed_is_valid(state, config):
        return SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_STALE)

    return SetSteeringAssistance(
        interpolate_steering_curve_definition(
            sample.speed_kph,
            active_definition,
        ),
        SteeringCommandReason.AUTO,
    )


def steering_command_for_active_curve(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance | None:
    """Recalculate only when activation can immediately affect Auto output."""

    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    if normal.mode is not SteeringMode.AUTO or isinstance(steering, MaximumAssistance):
        return None
    if not _speed_is_valid(state, config):
        return None
    return _steering_command(state, config, active_definition)


def _speed_is_valid(state: ApplicationState, config: SteeringConfig) -> bool:
    sample = state.speed_sample
    return (
        sample is not None
        and state.speed_evaluated_at - sample.observed_at <= config.speed_timeout_s
    )


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
