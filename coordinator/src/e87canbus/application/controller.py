"""Pure hardware-independent application decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import assert_never

from e87canbus.application.events import (
    BUTTON_FEEDBACK_BLINK_OFF_MS,
    BUTTON_FEEDBACK_BLINK_ON_MS,
    BUTTON_FEEDBACK_DURATION_S,
    BUTTON_LED_COUNT,
    RGB_AMBER,
    RGB_BLUE,
    RGB_OFF,
    RGB_RED,
    RGB_WHITE,
    ApplicationEffect,
    ApplicationEvent,
    ButtonCommandFailed,
    ButtonFeedbackColour,
    ButtonFeedbackDeadlineReached,
    ButtonLedState,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    HighBeamStrobeDeadlineReached,
    OilTemperatureObserved,
    SetButtonPadBreathe,
    SetButtonPadProgram,
    SetHighBeam,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
    TriggerButtonPadBlink,
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
from e87canbus.button_pad import (
    ButtonPadProgram,
    blink_track,
    breathe_track,
    resolved_button_pad_program,
    solid_track,
)
from e87canbus.config import EngineTelemetryConfig, HighBeamStrobeConfig, SteeringConfig
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    clamp_manual_level,
    interpolate_steering_curve_definition,
)

STEERING_MODE_BUTTON_INDEX = 0
MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3
DEMO_BREATHE_BUTTON_INDEX = 15
SERVOTRONIC_BUTTON_INDEXES = frozenset({0, 1, 2, 3})
SOFT_WHITE: tuple[int, int, int] = (8, 8, 8)
SOFT_AMBER: tuple[int, int, int] = (8, 6, 0)
DEMO_BREATHE_RGB: tuple[int, int, int] = (0, 220, 255)
DEMO_BREATHE_MINIMUM_BRIGHTNESS = 20
DEMO_BREATHE_MAXIMUM_BRIGHTNESS = 255
DEMO_BREATHE_PERIOD_MS = 1600


class EngineTelemetryStatus(StrEnum):
    VALID = "valid"
    NEVER_OBSERVED = "never_observed"
    STALE = "stale"


@dataclass(frozen=True)
class EngineTelemetryValue:
    value: int | float | None
    status: EngineTelemetryStatus


@dataclass(frozen=True)
class EngineTelemetrySnapshot:
    rpm: EngineTelemetryValue
    oil_temperature_c: EngineTelemetryValue
    coolant_temperature_c: EngineTelemetryValue


@dataclass(frozen=True)
class ApplicationSnapshot:
    vehicle_speed_kph: float
    steering_mode: SteeringMode
    manual_assistance_level: int
    manual_assistance_level_count: int
    maximum_assistance_active: bool
    speed_valid: bool
    engine: EngineTelemetrySnapshot
    active_steering_curve: ActiveSteeringCurve
    steering_curve_activation_status: SteeringCurveActivationStatus
    curve_activation_available: bool
    button_pad_program: ButtonPadProgram
    high_beam_enabled: bool
    high_beam_strobe_active: bool
    high_beam_strobe_cycles_remaining: int
    high_beam_next_transition_at: float | None


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
                    (_steering_command(next_state, config, active_definition),),
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
        case ButtonCommandFailed(button_index, occurred_at, blink_colour):
            deadlines: list[float | None] = list(state.button_feedback_deadlines)
            colours = list(state.button_feedback_colours)
            duration_s = (
                (BUTTON_FEEDBACK_BLINK_ON_MS + BUTTON_FEEDBACK_BLINK_OFF_MS) / 1000
                if blink_colour is ButtonFeedbackColour.WHITE
                else BUTTON_FEEDBACK_DURATION_S
            )
            deadlines[button_index] = occurred_at + duration_s
            colours[button_index] = blink_colour
            next_state = replace(
                state,
                button_feedback_deadlines=tuple(deadlines),
                button_feedback_colours=tuple(colours),
            )
            return Transition(next_state, (TriggerButtonPadBlink(button_index, blink_colour),))
        case ButtonFeedbackDeadlineReached(now):
            next_deadlines: tuple[float | None, ...] = tuple(
                None if deadline is not None and deadline <= now else deadline
                for deadline in state.button_feedback_deadlines
            )
            if next_deadlines == state.button_feedback_deadlines:
                return Transition(state)
            next_colours = tuple(
                None if deadline is not None and deadline <= now else colour
                for deadline, colour in zip(
                    state.button_feedback_deadlines,
                    state.button_feedback_colours,
                    strict=True,
                )
            )
            next_state = replace(
                state,
                button_feedback_deadlines=next_deadlines,
                button_feedback_colours=next_colours,
            )
            # Blink tracks carry final_rgb and stop themselves. Publishing the
            # cleared state is sufficient; transmitting a cleanup scene can
            # overwrite a blink that is still queued in the ISO-TP transport.
            return Transition(next_state)
        case _:
            assert_never(event)


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
        effects += (_steering_command(new_state, config, active_definition),)
    if new_state.high_beam_enabled != state.high_beam_enabled and not any(
        isinstance(effect, SetHighBeam) for effect in effects
    ):
        effects += (SetHighBeam(new_state.high_beam_enabled),)
    return Transition(new_state, effects)


def snapshot(
    state: ApplicationState,
    config: SteeringConfig,
    engine_config: EngineTelemetryConfig,
    active_curve: ActiveSteeringCurve,
    activation_status: SteeringCurveActivationStatus,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
    curve_activation_available: bool = False,
) -> ApplicationSnapshot:
    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
        manual_assistance_level_count=config.manual_level_count,
        maximum_assistance_active=maximum_active,
        speed_valid=_speed_is_valid(state, config),
        engine=EngineTelemetrySnapshot(
            rpm=_engine_value(
                None if state.engine_rpm_sample is None else state.engine_rpm_sample.rpm,
                None if state.engine_rpm_sample is None else state.engine_rpm_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
            oil_temperature_c=_engine_value(
                None
                if state.oil_temperature_sample is None
                else state.oil_temperature_sample.temperature_c,
                None
                if state.oil_temperature_sample is None
                else state.oil_temperature_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
            coolant_temperature_c=_engine_value(
                None
                if state.coolant_temperature_sample is None
                else state.coolant_temperature_sample.temperature_c,
                None
                if state.coolant_temperature_sample is None
                else state.coolant_temperature_sample.observed_at,
                state.engine_telemetry_evaluated_at,
                engine_config,
            ),
        ),
        active_steering_curve=active_curve,
        steering_curve_activation_status=activation_status,
        curve_activation_available=curve_activation_available,
        button_pad_program=button_pad_program(state, servotronic_usable, high_beam_button_index),
        high_beam_enabled=state.high_beam_enabled,
        high_beam_strobe_active=state.high_beam_strobe_cycles_remaining > 0,
        high_beam_strobe_cycles_remaining=state.high_beam_strobe_cycles_remaining,
        high_beam_next_transition_at=state.high_beam_next_transition_at,
    )


def initial_effects(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> tuple[ApplicationEffect, ...]:
    """Return the complete output projection for synchronization."""

    return (
        button_led_effect(state),
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


def clear_maximum_assistance(state: ApplicationState) -> Transition:
    """Remove only the temporary maximum override when its device is lost."""

    if not isinstance(state.steering, MaximumAssistance):
        return Transition(state)
    next_state = replace(state, steering=state.steering.previous)
    return Transition(next_state, _steering_state_effects(state, next_state))


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


def _steering_projection(
    state: ApplicationState,
    config: SteeringConfig,
) -> tuple[SteeringMode, int, bool]:
    steering = state.steering
    if isinstance(steering, MaximumAssistance):
        return SteeringMode.MANUAL, steering.previous.manual_level, True
    return steering.mode, steering.manual_level, False


def button_led_state(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> ButtonLedState:
    """Derive the complete button-pad LED projection from application state."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    mode_colour = (
        RGB_BLUE
        if servotronic_usable and mode is SteeringMode.AUTO
        else RGB_AMBER
        if servotronic_usable
        else SOFT_AMBER
    )
    maximum_colour = (
        RGB_WHITE
        if servotronic_usable and isinstance(state.steering, MaximumAssistance)
        else RGB_OFF
    )
    assigned_buttons = SERVOTRONIC_BUTTON_INDEXES | {
        high_beam_button_index,
        DEMO_BREATHE_BUTTON_INDEX,
    }
    normal = tuple(
        mode_colour
        if index == STEERING_MODE_BUTTON_INDEX
        else maximum_colour
        if index == MAXIMUM_ASSISTANCE_BUTTON_INDEX and maximum_colour != RGB_OFF
        else SOFT_AMBER
        if index in SERVOTRONIC_BUTTON_INDEXES and not servotronic_usable
        else SOFT_WHITE
        if index in assigned_buttons
        else RGB_OFF
        for index in range(BUTTON_LED_COUNT)
    )
    return ButtonLedState(normal)


def button_led_effect(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> SetButtonPadProgram:
    """Return the complete device program; static RGB remains the normal case.

    The frozen ``SetButtonPadProgram`` result is shareable, so callers that need
    it more than once in a single commit compute it once and reuse the local.
    """

    displayed = button_led_state(state, servotronic_usable, high_beam_button_index).rgb
    tracks = [solid_track(rgb) for rgb in displayed]
    if state.button_pad_demo_breathe_enabled:
        tracks[DEMO_BREATHE_BUTTON_INDEX] = breathe_track(
            DEMO_BREATHE_RGB,
            DEMO_BREATHE_MINIMUM_BRIGHTNESS,
            DEMO_BREATHE_MAXIMUM_BRIGHTNESS,
            DEMO_BREATHE_PERIOD_MS,
            final_rgb=displayed[DEMO_BREATHE_BUTTON_INDEX],
        )
    feedback_rgb = {
        ButtonFeedbackColour.RED: RGB_RED,
        ButtonFeedbackColour.AMBER: RGB_AMBER,
        ButtonFeedbackColour.WHITE: RGB_WHITE,
    }
    for index, colour in enumerate(state.button_feedback_colours):
        if colour is not None:
            tracks[index] = blink_track(
                feedback_rgb[colour],
                BUTTON_FEEDBACK_BLINK_ON_MS,
                BUTTON_FEEDBACK_BLINK_OFF_MS,
                1 if colour is ButtonFeedbackColour.WHITE else 2,
                displayed[index],
            )
    return SetButtonPadProgram(resolved_button_pad_program(tuple(tracks)))


def button_pad_program(
    state: ApplicationState,
    servotronic_usable: bool = True,
    high_beam_button_index: int = HighBeamStrobeConfig().button_index,
) -> ButtonPadProgram:
    return button_led_effect(state, servotronic_usable, high_beam_button_index).program


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


def steering_command_for_current_state(
    state: ApplicationState,
    config: SteeringConfig,
    active_definition: SteeringCurveDefinition,
) -> SetSteeringAssistance:
    """Build the complete retained command for Servotronic activation sync."""

    return _steering_command(state, config, active_definition)


def _speed_is_valid(state: ApplicationState, config: SteeringConfig) -> bool:
    sample = state.speed_sample
    return (
        sample is not None
        and state.speed_evaluated_at - sample.observed_at <= config.speed_timeout_s
    )


def _engine_value(
    value: int | float | None,
    observed_at: float | None,
    evaluated_at: float,
    config: EngineTelemetryConfig,
) -> EngineTelemetryValue:
    if observed_at is None:
        return EngineTelemetryValue(None, EngineTelemetryStatus.NEVER_OBSERVED)
    if evaluated_at - observed_at > config.timeout_s:
        return EngineTelemetryValue(None, EngineTelemetryStatus.STALE)
    return EngineTelemetryValue(value, EngineTelemetryStatus.VALID)


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
