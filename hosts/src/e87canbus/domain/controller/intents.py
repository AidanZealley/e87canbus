"""Apply operator and button intents to desired coordinator steering state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.config import SteeringConfig
from e87canbus.domain.controller.reducer import Transition
from e87canbus.domain.intents import (
    AdjustManualAssistance,
    OperatorIntent,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    ToggleAutomaticAssistance,
    ToggleMaximumAssistance,
)
from e87canbus.domain.intents import (
    SetMaximumAssistance as SetMaximumAssistanceIntent,
)
from e87canbus.domain.state import (
    ApplicationState,
    MaximumAssistance,
    SteeringMode,
    SteeringState,
)
from e87canbus.domain.steering.curves import (
    clamp_manual_level,
)


def execute_operator_intent(
    state: ApplicationState, intent: OperatorIntent, config: SteeringConfig
) -> Transition:
    """Apply one operator request to desired coordinator state."""
    return _apply_operator_intent(state, intent, config)


def _apply_operator_intent(
    state: ApplicationState,
    intent: OperatorIntent,
    config: SteeringConfig,
) -> Transition:
    """Apply one transport-independent operator request to authoritative state."""

    match intent:
        case SelectSteeringMode(mode):
            return _select_steering_mode(state, mode, config)
        case ToggleAutomaticAssistance():
            return Transition(_toggled_automatic_assistance(state))
        case AdjustManualAssistance(delta):
            return Transition(_establish_manual_assistance(state, _AdjustLevel(delta), config))
        case SetManualAssistanceLevel(level):
            return Transition(_establish_manual_assistance(state, _SelectLevel(level), config))
        case SetMaximumAssistanceIntent(enabled):
            return _set_maximum_assistance(state, enabled)
        case ToggleMaximumAssistance():
            return Transition(_toggled_maximum_assistance(state))
        case _:
            assert_never(intent)


def _toggled_automatic_assistance(state: ApplicationState) -> ApplicationState:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return replace(
            state,
            steering=replace(steering.previous, mode=SteeringMode.AUTO),
        )
    mode = SteeringMode.MANUAL if steering.mode is SteeringMode.AUTO else SteeringMode.AUTO
    new_state = replace(state, steering=replace(steering, mode=mode))
    return new_state


@dataclass(frozen=True)
class _RestoreLevel:
    pass


@dataclass(frozen=True)
class _AdjustLevel:
    delta: int


@dataclass(frozen=True)
class _SelectLevel:
    level: int


_ManualAssistanceChange = _RestoreLevel | _AdjustLevel | _SelectLevel


def _establish_manual_assistance(
    state: ApplicationState,
    change: _ManualAssistanceChange,
    config: SteeringConfig,
) -> ApplicationState:
    """Cancel Max, select Manual, and apply one unambiguous level operation."""

    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    remembered_level = clamp_manual_level(normal.manual_level, config.manual_level_count)
    match change:
        case _RestoreLevel():
            level = remembered_level
        case _AdjustLevel(delta):
            # The first relative request from Max or Auto only restores Manual.
            level = (
                remembered_level
                if isinstance(steering, MaximumAssistance) or normal.mode is SteeringMode.AUTO
                else clamp_manual_level(remembered_level + delta, config.manual_level_count)
            )
        case _SelectLevel(level):
            if not 0 <= level < config.manual_level_count:
                raise ValueError(
                    f"manual assistance level must be between 0 and {config.manual_level_count - 1}"
                )
        case _:
            assert_never(change)
    return replace(state, steering=replace(normal, mode=SteeringMode.MANUAL, manual_level=level))


def _toggled_maximum_assistance(
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


def _set_maximum_assistance(
    state: ApplicationState,
    enabled: bool,
) -> Transition:
    steering = state.steering
    next_steering: SteeringState
    if enabled:
        next_steering = (
            steering
            if isinstance(steering, MaximumAssistance)
            else MaximumAssistance(previous=steering)
        )
    else:
        next_steering = steering.previous if isinstance(steering, MaximumAssistance) else steering
    next_state = replace(state, steering=next_steering)
    return Transition(next_state)


def _select_steering_mode(
    state: ApplicationState,
    mode: SteeringMode,
    config: SteeringConfig,
) -> Transition:
    if not isinstance(mode, SteeringMode):
        raise ValueError("mode must be a supported SteeringMode value")
    if mode is SteeringMode.MANUAL:
        next_state = _establish_manual_assistance(state, _RestoreLevel(), config)
        return Transition(next_state)
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    next_normal = replace(normal, mode=mode)
    # An explicit mode selection returns to normal steering, so it also
    # cancels the temporary maximum-assistance override.
    next_state = replace(state, steering=next_normal)
    return Transition(next_state)
