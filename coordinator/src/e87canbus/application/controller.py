"""Pure hardware-independent application decisions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from functools import lru_cache
from typing import assert_never

from e87canbus.application.events import (
    BUTTON_FEEDBACK_BLINK_OFF_MS,
    BUTTON_FEEDBACK_BLINK_ON_MS,
    BUTTON_FEEDBACK_BLINK_REPEAT,
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
    ButtonPressed,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    HighBeamStrobeDeadlineReached,
    MaximumAssistanceSet,
    OilTemperatureObserved,
    SetButtonPadProgram,
    SetButtonPadBreathe,
    SetHighBeam,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
    SteeringModeSet,
    TriggerButtonPadBlink,
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
    ActiveSteeringCurve,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    clamp_manual_level,
    interpolate_steering_curve_definition,
)

STEERING_MODE_BUTTON_INDEX = 0
MAXIMUM_ASSISTANCE_BUTTON_INDEX = 3
GRADIENT_TOGGLE_BUTTON_INDEX = 12
DEMO_BREATHE_BUTTON_INDEX = 15
SERVOTRONIC_BUTTON_INDEXES = frozenset({0, 1, 2, 3})
BUTTON_PAD_COLUMNS = 4
GRADIENT_CYAN: tuple[int, int, int] = (0, 220, 255)
GRADIENT_PINK: tuple[int, int, int] = (255, 0, 160)
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
    maximum_assistance_active: bool
    speed_valid: bool
    engine: EngineTelemetrySnapshot
    active_steering_curve: ActiveSteeringCurve
    steering_curve_activation_status: SteeringCurveActivationStatus
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
        case MaximumAssistanceSet(enabled):
            return _set_maximum_assistance(state, enabled)
        case SteeringModeSet(mode, manual_level):
            return _set_steering_mode(state, mode, manual_level, config)
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
            deadlines[button_index] = occurred_at + BUTTON_FEEDBACK_DURATION_S
            next_state = replace(state, button_feedback_deadlines=tuple(deadlines))
            return Transition(next_state, (TriggerButtonPadBlink(button_index, blink_colour),))
        case ButtonFeedbackDeadlineReached(now):
            next_deadlines: tuple[float | None, ...] = tuple(
                None if deadline is not None and deadline <= now else deadline
                for deadline in state.button_feedback_deadlines
            )
            if next_deadlines == state.button_feedback_deadlines:
                return Transition(state)
            next_state = replace(state, button_feedback_deadlines=next_deadlines)
            # Blink tracks carry final_rgb and stop themselves. Publishing the
            # cleared state is sufficient; transmitting a cleanup scene can
            # overwrite a blink that is still queued in the ISO-TP transport.
            return Transition(next_state)
        case ButtonPressed(button_index, observed_at):
            strobe_config = high_beam_strobe_config or HighBeamStrobeConfig()
            available_buttons = SERVOTRONIC_BUTTON_INDEXES | {
                strobe_config.button_index,
                GRADIENT_TOGGLE_BUTTON_INDEX,
                DEMO_BREATHE_BUTTON_INDEX,
            }
            if button_index not in available_buttons:
                return transition(
                    state,
                    ButtonCommandFailed(button_index, observed_at, ButtonFeedbackColour.WHITE),
                    config,
                    active_definition,
                    high_beam_strobe_config,
                )
            new_state = _button_transition(
                state,
                button_index,
                observed_at,
                config,
                strobe_config,
            )
            previous_leds = button_led_effect(state)
            new_leds = button_led_effect(new_state)
            effects: tuple[ApplicationEffect, ...] = ()
            if new_leds != previous_leds:
                effects += (
                    SetButtonPadBreathe(
                        DEMO_BREATHE_BUTTON_INDEX,
                        new_state.button_pad_demo_breathe_enabled,
                    ),
                ) if (
                    new_state.button_pad_demo_breathe_enabled
                    != state.button_pad_demo_breathe_enabled
                ) else (new_leds,)
            if new_state.steering != state.steering:
                effects += (_steering_command(new_state, config, active_definition),)
            if new_state.high_beam_enabled != state.high_beam_enabled:
                effects += (SetHighBeam(new_state.high_beam_enabled),)
            return Transition(new_state, effects)
        case _:
            assert_never(event)


def snapshot(
    state: ApplicationState,
    config: SteeringConfig,
    engine_config: EngineTelemetryConfig,
    active_curve: ActiveSteeringCurve,
    activation_status: SteeringCurveActivationStatus,
) -> ApplicationSnapshot:
    mode, manual_level, maximum_active = _steering_projection(state, config)
    sample = state.speed_sample
    return ApplicationSnapshot(
        vehicle_speed_kph=sample.speed_kph if sample is not None else 0.0,
        steering_mode=mode,
        manual_assistance_level=manual_level,
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
        button_pad_program=button_pad_program(state),
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


def _button_transition(
    state: ApplicationState,
    button_index: int,
    observed_at: float,
    config: SteeringConfig,
    high_beam_strobe_config: HighBeamStrobeConfig,
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
        case index if index == high_beam_strobe_config.button_index:
            return _start_high_beam_strobe(state, observed_at, high_beam_strobe_config)
        case index if index == GRADIENT_TOGGLE_BUTTON_INDEX:
            return replace(
                state,
                button_pad_gradient_enabled=not state.button_pad_gradient_enabled,
            )
        case index if index == DEMO_BREATHE_BUTTON_INDEX:
            return replace(
                state,
                button_pad_demo_breathe_enabled=not state.button_pad_demo_breathe_enabled,
            )
        case _:
            return state


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


def _set_steering_mode(
    state: ApplicationState,
    mode: SteeringMode,
    manual_level: int | None,
    config: SteeringConfig,
) -> Transition:
    if not isinstance(mode, SteeringMode):
        raise ValueError("mode must be a supported SteeringMode value")
    if manual_level is not None:
        if type(manual_level) is not int:
            raise ValueError("manual_level must be an integer")
        if not 0 <= manual_level < config.manual_level_count:
            raise ValueError(f"manual_level must be between 0 and {config.manual_level_count - 1}")
    steering = state.steering
    normal = steering.previous if isinstance(steering, MaximumAssistance) else steering
    next_normal = replace(
        normal,
        mode=mode,
        manual_level=normal.manual_level if manual_level is None else manual_level,
    )
    next_state = replace(
        state,
        steering=(
            MaximumAssistance(previous=next_normal)
            if isinstance(steering, MaximumAssistance)
            else next_normal
        ),
    )
    return Transition(next_state, _steering_state_effects(state, next_state))


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
        return SteeringMode.MANUAL, config.manual_level_count - 1, True
    return steering.mode, steering.manual_level, False


def button_led_state(state: ApplicationState) -> ButtonLedState:
    """Derive the complete button-pad LED projection from application state."""

    steering = state.steering
    mode = SteeringMode.MANUAL if isinstance(steering, MaximumAssistance) else steering.mode
    mode_colour = RGB_BLUE if mode is SteeringMode.AUTO else RGB_AMBER
    maximum_colour = RGB_WHITE if isinstance(state.steering, MaximumAssistance) else RGB_OFF
    normal = tuple(
        mode_colour
        if index == STEERING_MODE_BUTTON_INDEX
        else maximum_colour
        if index == MAXIMUM_ASSISTANCE_BUTTON_INDEX
        else RGB_OFF
        for index in range(BUTTON_LED_COUNT)
    )
    return ButtonLedState(
        tuple(
            RGB_RED if deadline is not None else normal[index]
            for index, deadline in enumerate(state.button_feedback_deadlines)
        )
    )


@lru_cache(maxsize=16)
def button_led_effect(state: ApplicationState) -> SetButtonPadProgram:
    """Return the complete device program; static RGB remains the normal case.

    Memoized because a single commit compares the effect for the same state
    several times; the frozen ``SetButtonPadProgram`` result is safe to share.
    """

    displayed = (
        static_cyan_to_pink_gradient()
        if state.button_pad_gradient_enabled
        else button_led_state(replace(state, button_feedback_deadlines=(None,) * 16)).rgb
    )
    tracks = [solid_track(rgb) for rgb in displayed]
    if state.button_pad_demo_breathe_enabled:
        tracks[DEMO_BREATHE_BUTTON_INDEX] = breathe_track(
            DEMO_BREATHE_RGB,
            DEMO_BREATHE_MINIMUM_BRIGHTNESS,
            DEMO_BREATHE_MAXIMUM_BRIGHTNESS,
            DEMO_BREATHE_PERIOD_MS,
            final_rgb=displayed[DEMO_BREATHE_BUTTON_INDEX],
        )
    for index, deadline in enumerate(state.button_feedback_deadlines):
        if deadline is not None:
            # Device self-terminates this blink to displayed[index]; the feedback deadline
            # resyncs coordinator state to solid so the two stay converged (see events.py).
            tracks[index] = blink_track(
                RGB_RED,
                BUTTON_FEEDBACK_BLINK_ON_MS,
                BUTTON_FEEDBACK_BLINK_OFF_MS,
                BUTTON_FEEDBACK_BLINK_REPEAT,
                displayed[index],
            )
    return SetButtonPadProgram(resolved_button_pad_program(tuple(tracks)))


def button_pad_program(state: ApplicationState) -> ButtonPadProgram:
    return button_led_effect(state).program


def static_cyan_to_pink_gradient() -> tuple[tuple[int, int, int], ...]:
    """Return a left-to-right cyan-to-pink gradient for the 4×4 pad."""

    def channel(start: int, end: int, column: int) -> int:
        return start + ((end - start) * column) // (BUTTON_PAD_COLUMNS - 1)

    return tuple(
        (
            channel(GRADIENT_CYAN[0], GRADIENT_PINK[0], index % BUTTON_PAD_COLUMNS),
            channel(GRADIENT_CYAN[1], GRADIENT_PINK[1], index % BUTTON_PAD_COLUMNS),
            channel(GRADIENT_CYAN[2], GRADIENT_PINK[2], index % BUTTON_PAD_COLUMNS),
        )
        for index in range(BUTTON_LED_COUNT)
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
