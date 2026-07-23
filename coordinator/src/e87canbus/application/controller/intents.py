"""Applying operator intents to authoritative state and completing their effects.

``execute_operator_intent`` owns the behaviour of every operator request and
returns a self-contained result (LED program plus the implied actuator commands).
``finish_button_intent`` layers button-origin presentation onto that result.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from e87canbus.application.controller.button_leds import (
    DEMO_BREATHE_BUTTON_INDEX,
    MAXIMUM_ASSISTANCE_BUTTON_INDEX,
    button_led_effect,
    button_led_state,
)
from e87canbus.application.controller.reducer import Transition, transition
from e87canbus.application.controller.steering import steering_command
from e87canbus.application.events import (
    ApplicationEffect,
    ButtonCommandFailed,
    ButtonFeedbackColour,
    SetButtonPadBreathe,
    SetButtonPadProgram,
    SetHighBeam,
    SetSteeringAssistance,
)
from e87canbus.application.intents import (
    DEFAULT_OPERATOR_INTENT_CONTEXT,
    AdjustManualAssistance,
    OperatorIntent,
    OperatorIntentContext,
    SelectSteeringMode,
    SetManualAssistanceLevel,
    StartHighBeamStrobe,
    ToggleAutomaticAssistance,
    ToggleButtonPadDemoBreathe,
    ToggleMaximumAssistance,
)
from e87canbus.application.intents import (
    SetMaximumAssistance as SetMaximumAssistanceIntent,
)
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    SteeringMode,
    SteeringState,
)
from e87canbus.config import HighBeamStrobeConfig, SteeringConfig
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    SteeringCurveDefinition,
    clamp_manual_level,
)


def execute_operator_intent(
    state: ApplicationState,
    intent: OperatorIntent,
    config: SteeringConfig,
    context: OperatorIntentContext = DEFAULT_OPERATOR_INTENT_CONTEXT,
    *,
    active_definition: SteeringCurveDefinition = BUILT_IN_STEERING_CURVE,
    high_beam_strobe_config: HighBeamStrobeConfig | None = None,
) -> Transition:
    """Apply one operator request and return its complete origin-neutral effects.

    Adapters are responsible for availability checks and origin-specific feedback.
    This function owns the behavior of the request itself (including the steering
    invariants shared by exact API selections and relative button-pad actions) and
    returns a self-contained result: the LED program plus the ``SetSteeringAssistance``
    and ``SetHighBeam`` actuator commands implied by the state change. No mandatory
    post-pass is required for the effect set to be complete.
    """

    result = _apply_operator_intent(
        state,
        intent,
        config,
        context,
        high_beam_strobe_config=high_beam_strobe_config,
    )
    return _complete_operator_effects(state, result, config, active_definition)


def finish_button_intent(
    state: ApplicationState,
    intent_result: Transition,
    button_index: int,
    observed_at: float,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
    high_beam_strobe_config: HighBeamStrobeConfig,
) -> Transition:
    """Layer button-origin presentation onto an already-complete intent result.

    ``intent_result`` is the self-contained output of ``execute_operator_intent``;
    this only substitutes the button-LED program for the pressing origin and adds a
    white confirmation blink when nothing the operator can see actually changed.
    """
    high_beam_button_index = high_beam_strobe_config.button_index
    new_state = intent_result.state
    previous_leds = button_led_effect(state, high_beam_button_index=high_beam_button_index)
    new_leds = button_led_effect(new_state, high_beam_button_index=high_beam_button_index)
    effects = tuple(
        new_leds if isinstance(effect, SetButtonPadProgram) else effect
        for effect in intent_result.effects
    )
    demo_breathe_changed = (
        new_state.button_pad_demo_breathe_enabled != state.button_pad_demo_breathe_enabled
    )
    if new_leds != previous_leds and not any(
        isinstance(effect, (SetButtonPadProgram, SetButtonPadBreathe)) for effect in effects
    ):
        effects += (
            (
                SetButtonPadBreathe(
                    DEMO_BREATHE_BUTTON_INDEX,
                    new_state.button_pad_demo_breathe_enabled,
                ),
            )
            if demo_breathe_changed
            else (new_leds,)
        )
    previous_led_state = button_led_state(state, high_beam_button_index=high_beam_button_index)
    new_led_state = button_led_state(new_state, high_beam_button_index=high_beam_button_index)
    button_visual_changed = new_led_state.rgb[button_index] != previous_led_state.rgb[
        button_index
    ] or (button_index == DEMO_BREATHE_BUTTON_INDEX and demo_breathe_changed)
    # A manual-assistance press can cancel the maximum-assistance override. In
    # that case the persistent program replaces button 3 without a racing blink.
    maximum_indicator_changed = (
        new_led_state.rgb[MAXIMUM_ASSISTANCE_BUTTON_INDEX]
        != previous_led_state.rgb[MAXIMUM_ASSISTANCE_BUTTON_INDEX]
    )
    if not button_visual_changed and not maximum_indicator_changed:
        feedback = transition(
            new_state,
            ButtonCommandFailed(button_index, observed_at, ButtonFeedbackColour.WHITE),
            config,
            active_definition,
            high_beam_strobe_config,
        )
        new_state = feedback.state
        effects += feedback.effects
    return Transition(new_state, effects)


def clear_maximum_assistance(state: ApplicationState) -> Transition:
    """Remove only the temporary maximum override when its device is lost."""

    if not isinstance(state.steering, MaximumAssistance):
        return Transition(state)
    next_state = replace(state, steering=state.steering.previous)
    return Transition(next_state, _steering_state_effects(state, next_state))


def _apply_operator_intent(
    state: ApplicationState,
    intent: OperatorIntent,
    config: SteeringConfig,
    context: OperatorIntentContext,
    *,
    high_beam_strobe_config: HighBeamStrobeConfig | None,
) -> Transition:
    """Apply one transport-independent operator request to authoritative state."""

    match intent:
        case SelectSteeringMode(mode):
            return _select_steering_mode(state, mode, config)
        case ToggleAutomaticAssistance():
            return _finish_steering_intent(state, _toggled_automatic_assistance(state))
        case AdjustManualAssistance(delta):
            return _finish_steering_intent(
                state,
                _establish_manual_assistance(state, _AdjustLevel(delta), config),
            )
        case SetManualAssistanceLevel(level):
            return _finish_steering_intent(
                state,
                _establish_manual_assistance(state, _SelectLevel(level), config),
            )
        case SetMaximumAssistanceIntent(enabled):
            return _set_maximum_assistance(state, enabled)
        case ToggleMaximumAssistance():
            return _finish_steering_intent(state, _toggled_maximum_assistance(state))
        case StartHighBeamStrobe():
            if context.observed_at is None:
                raise ValueError("observed_at is required to start the high-beam strobe")
            strobe_config = high_beam_strobe_config or HighBeamStrobeConfig()
            next_state = _start_high_beam_strobe(state, context.observed_at, strobe_config)
            effects: tuple[ApplicationEffect, ...] = ()
            if next_state.high_beam_enabled != state.high_beam_enabled:
                effects = (SetHighBeam(next_state.high_beam_enabled),)
            return Transition(next_state, effects)
        case ToggleButtonPadDemoBreathe():
            next_state = replace(
                state,
                button_pad_demo_breathe_enabled=not state.button_pad_demo_breathe_enabled,
            )
            return Transition(
                next_state,
                (
                    SetButtonPadBreathe(
                        DEMO_BREATHE_BUTTON_INDEX,
                        next_state.button_pad_demo_breathe_enabled,
                    ),
                ),
            )
        case _:
            assert_never(intent)


def _complete_operator_effects(
    state: ApplicationState,
    intent_result: Transition,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> Transition:
    """Append the actuator effects implied by a state change, without duplicating.

    Called by ``execute_operator_intent`` so its result is complete on its own; the
    LED-program effects are produced inline by each intent, and this adds the
    ``SetSteeringAssistance``/``SetHighBeam`` commands only when the relevant state
    changed and the intent did not already emit them.
    """

    effects = intent_result.effects
    new_state = intent_result.state
    if new_state.steering != state.steering and not any(
        isinstance(effect, SetSteeringAssistance) for effect in effects
    ):
        effects += (steering_command(new_state, config, active_definition),)
    if new_state.high_beam_enabled != state.high_beam_enabled and not any(
        isinstance(effect, SetHighBeam) for effect in effects
    ):
        effects += (SetHighBeam(new_state.high_beam_enabled),)
    return Transition(new_state, effects)


def _start_high_beam_strobe(
    state: ApplicationState,
    observed_at: float,
    config: HighBeamStrobeConfig,
) -> ApplicationState:
    """Start a plan from the ingress timestamp; active plans are intentionally unchanged."""

    if state.high_beam_strobe_cycles_remaining > 0:
        return state
    return replace(
        state,
        high_beam_enabled=True,
        high_beam_strobe_cycles_remaining=config.cycle_count,
        high_beam_next_transition_at=observed_at + config.asserted_duration_s,
    )


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
    return Transition(next_state, _steering_state_effects(state, next_state))


def _select_steering_mode(
    state: ApplicationState,
    mode: SteeringMode,
    config: SteeringConfig,
) -> Transition:
    if not isinstance(mode, SteeringMode):
        raise ValueError("mode must be a supported SteeringMode value")
    if mode is SteeringMode.MANUAL:
        next_state = _establish_manual_assistance(state, _RestoreLevel(), config)
        return Transition(next_state, _steering_state_effects(state, next_state))
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    next_normal = replace(normal, mode=mode)
    # An explicit mode selection is a normal steering command, so it also
    # cancels the temporary maximum-assistance override.
    next_state = replace(state, steering=next_normal)
    return Transition(next_state, _steering_state_effects(state, next_state))


def _finish_steering_intent(
    previous: ApplicationState,
    current: ApplicationState,
) -> Transition:
    return Transition(current, _steering_state_effects(previous, current))


def _steering_state_effects(
    previous: ApplicationState,
    current: ApplicationState,
) -> tuple[ApplicationEffect, ...]:
    previous_effect = button_led_effect(previous)
    current_effect = button_led_effect(current)
    return () if previous_effect == current_effect else (current_effect,)
