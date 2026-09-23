"""Applying operator intents to authoritative state and completing their effects.

``execute_operator_intent`` owns the behaviour of every operator request and
returns a self-contained result (the implied actuator commands).
Button presses use the same intent transition as operator commands.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.config import SteeringConfig
from e87canbus.domain.controller.reducer import Transition
from e87canbus.domain.controller.steering import steering_command
from e87canbus.domain.events import (
    SetSteeringAssistance,
)
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
    BUILT_IN_STEERING_CURVE,
    SteeringCurveDefinition,
    clamp_manual_level,
)


def execute_operator_intent(
    state: ApplicationState,
    intent: OperatorIntent,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition = BUILT_IN_STEERING_CURVE,
) -> Transition:
    """Apply one operator request and return its complete origin-neutral effects.

    Adapters are responsible for availability checks.
    This function owns the behavior of the request itself (including the steering
    invariants shared by exact API selections and relative button-pad actions) and
    returns the steering actuator command implied by the state change.
    """

    result = _apply_operator_intent(state, intent, config)
    return _complete_operator_effects(state, result, config, active_definition)


def clear_maximum_assistance(
    state: ApplicationState,
) -> Transition:
    """Remove only the temporary maximum override when its device is lost."""

    if not isinstance(state.steering, MaximumAssistance):
        return Transition(state)
    next_state = replace(state, steering=state.steering.previous)
    return Transition(next_state)


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
            return _finish_steering_intent(state, _toggled_automatic_assistance(state))
        case AdjustManualAssistance(delta):
            return _finish_steering_intent(
                state, _establish_manual_assistance(state, _AdjustLevel(delta), config)
            )
        case SetManualAssistanceLevel(level):
            return _finish_steering_intent(
                state, _establish_manual_assistance(state, _SelectLevel(level), config)
            )
        case SetMaximumAssistanceIntent(enabled):
            return _set_maximum_assistance(state, enabled)
        case ToggleMaximumAssistance():
            return _finish_steering_intent(state, _toggled_maximum_assistance(state))
        case _:
            assert_never(intent)


def _complete_operator_effects(
    state: ApplicationState,
    intent_result: Transition,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> Transition:
    """Append the actuator effects implied by a state change, without duplicating.

    Called by ``execute_operator_intent`` so its result contains the steering
    command when state changed and the intent did not emit it.
    """

    effects = intent_result.effects
    new_state = intent_result.state
    if new_state.steering != state.steering and not any(
        isinstance(effect, SetSteeringAssistance) for effect in effects
    ):
        effects += (steering_command(new_state, config, active_definition),)
    return Transition(new_state, effects)


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
    # An explicit mode selection is a normal steering command, so it also
    # cancels the temporary maximum-assistance override.
    next_state = replace(state, steering=next_normal)
    return Transition(next_state)


def _finish_steering_intent(
    previous: ApplicationState,
    current: ApplicationState,
) -> Transition:
    return Transition(current)
