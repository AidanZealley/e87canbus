"""Pure hardware-independent application decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace

from e87canbus.application.events import (
    ApplicationEffect,
    ApplicationEvent,
    ControlTimerElapsed,
    LedColour,
    SetButtonLed,
    SpeedObserved,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    SteeringMode,
)
from e87canbus.config import SteeringConfig
from e87canbus.features.steering import clamp_manual_level

STEERING_MODE_BUTTON_INDEX = 0
MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    maximum_assistance_active: bool
    speed_valid: bool


@dataclass(frozen=True)
class Transition:
    state: ApplicationState
    effects: tuple[ApplicationEffect, ...] = ()


def transition(
    state: ApplicationState,
    event: ApplicationEvent,
    config: SteeringConfig,
) -> Transition:
    """Return the complete next state and ordered effects for one event."""

    if isinstance(event, SpeedObserved):
        return Transition(
            replace(
                state,
                speed_sample=replace(event.sample, speed_kph=max(0.0, event.sample.speed_kph)),
                speed_evaluated_at=event.sample.observed_at,
            )
        )
    if isinstance(event, ControlTimerElapsed):
        return Transition(replace(state, speed_evaluated_at=event.now))

    match event.button_index:
        case 0:
            return _toggle_steering_mode(state)
        case 1:
            return _adjust_assistance(state, -1, config)
        case 2:
            return _adjust_assistance(state, 1, config)
        case 3:
            return _toggle_maximum_assistance(state)
        case _:
            return Transition(state)


def snapshot(state: ApplicationState, config: SteeringConfig) -> ApplicationSnapshot:
    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
        maximum_assistance_active=maximum_active,
        speed_valid=(
            sample is not None
            and state.speed_evaluated_at - sample.observed_at <= config.speed_timeout_s
        ),
    )


def initial_effects(state: ApplicationState) -> tuple[ApplicationEffect, ...]:
    """Return the complete verified output projection for synchronization."""

    return (_steering_mode_led(state), _maximum_assistance_led(state))


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


def _toggle_steering_mode(state: ApplicationState) -> Transition:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return Transition(state)
    mode = SteeringMode.MANUAL if steering.mode is SteeringMode.AUTO else SteeringMode.AUTO
    new_state = replace(state, steering=replace(steering, mode=mode))
    return Transition(new_state, (_steering_mode_led(new_state),))


def _adjust_assistance(
    state: ApplicationState,
    delta: int,
    config: SteeringConfig,
) -> Transition:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        new_state = replace(
            state,
            steering=replace(steering.previous, mode=SteeringMode.MANUAL),
        )
        return Transition(
            new_state,
            (_steering_mode_led(new_state), _maximum_assistance_led(new_state)),
        )
    if steering.mode is SteeringMode.AUTO:
        new_state = replace(state, steering=replace(steering, mode=SteeringMode.MANUAL))
        return Transition(new_state, (_steering_mode_led(new_state),))

    manual_level = clamp_manual_level(
        steering.manual_level + delta,
        config.manual_level_count,
    )
    return Transition(replace(state, steering=replace(steering, manual_level=manual_level)))


def _toggle_maximum_assistance(
    state: ApplicationState,
) -> Transition:
    steering = state.steering
    new_state = replace(
        state,
        steering=(
            steering.previous
            if isinstance(steering, MaximumAssistance)
            else MaximumAssistance(previous=steering)
        ),
    )
    return Transition(
        new_state,
        (_steering_mode_led(new_state), _maximum_assistance_led(new_state)),
    )


def _steering_projection(
    state: ApplicationState,
    config: SteeringConfig,
) -> tuple[SteeringMode, int, bool]:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SteeringMode.MANUAL, config.manual_level_count - 1, True
    return steering.mode, steering.manual_level, False


def _steering_mode_led(state: ApplicationState) -> SetButtonLed:
    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    return SetButtonLed(
        button_index=STEERING_MODE_BUTTON_INDEX,
        colour=LedColour.BLUE if mode is SteeringMode.AUTO else LedColour.AMBER,
    )


def _maximum_assistance_led(state: ApplicationState) -> SetButtonLed:
    return SetButtonLed(
        button_index=MAXIMUM_ASSISTANCE_BUTTON_INDEX,
        colour=(
            LedColour.WHITE
            if isinstance(state.steering, MaximumAssistance)
            else LedColour.OFF
        ),
    )
