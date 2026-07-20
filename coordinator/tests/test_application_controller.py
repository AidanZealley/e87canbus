from dataclasses import FrozenInstanceError, replace

import pytest
from e87canbus.application import controller
from e87canbus.application.controller import (
    ApplicationSnapshot,
    EngineTelemetrySnapshot,
    EngineTelemetryStatus,
    EngineTelemetryValue,
    Transition,
    normalize_state,
)
from e87canbus.application.events import (
    RGB_AMBER,
    RGB_BLUE,
    RGB_OFF,
    RGB_WHITE,
    ApplicationEffect,
    ApplicationEvent,
    ButtonLedState,
    ButtonPressed,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    HighBeamStrobeDeadlineReached,
    OilTemperatureObserved,
    SetButtonPadProgram,
    SetButtonPadBreathe,
    SetHighBeam,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
    TriggerButtonPadBlink,
)
from e87canbus.application.state import (
    ApplicationState,
    CoolantTemperatureSample,
    EngineRpmSample,
    MaximumAssistance,
    NormalSteering,
    OilTemperatureSample,
    SpeedSample,
    SteeringMode,
)
from e87canbus.button_pad import solid_track, static_button_pad_program
from e87canbus.config import (
    CanNetwork,
    EngineTelemetryConfig,
    HighBeamStrobeConfig,
    SteeringConfig,
)
from e87canbus.features.steering import (
    ASSISTANCE_QUANTIZATION_TOLERANCE,
    SteeringCurveActivationStatus,
    default_steering_curve_definition,
    initial_active_steering_curve,
)

CONFIG = SteeringConfig()
ENGINE_CONFIG = EngineTelemetryConfig()
ACTIVE_CURVE = initial_active_steering_curve()
CURVE_DEFINITION = default_steering_curve_definition()
AUTO_LEDS = ButtonLedState((RGB_BLUE,) + (RGB_OFF,) * 15)
MANUAL_LEDS = ButtonLedState((RGB_AMBER,) + (RGB_OFF,) * 15)
MANUAL_MAXIMUM_LEDS = ButtonLedState((RGB_AMBER, RGB_OFF, RGB_OFF, RGB_WHITE) + (RGB_OFF,) * 12)


def static_effect(leds: ButtonLedState) -> SetButtonPadProgram:
    return SetButtonPadProgram(static_button_pad_program(leds.rgb))


def snapshot(state: ApplicationState, config: SteeringConfig) -> ApplicationSnapshot:
    return controller.snapshot(
        state,
        config,
        ENGINE_CONFIG,
        ACTIVE_CURVE,
        SteeringCurveActivationStatus.ACTIVE,
    )


def transition(
    state: ApplicationState,
    event: ApplicationEvent,
    config: SteeringConfig,
) -> Transition:
    return controller.transition(state, event, config, CURVE_DEFINITION)


def initial_effects(
    state: ApplicationState,
    config: SteeringConfig,
) -> tuple[ApplicationEffect, ...]:
    return controller.initial_effects(state, config, CURVE_DEFINITION)


def application_state(
    mode: SteeringMode = SteeringMode.AUTO,
    manual_level: int = 0,
) -> ApplicationState:
    return ApplicationState(steering=NormalSteering(mode, manual_level))


def projection(state: ApplicationState) -> tuple[SteeringMode, int, bool]:
    value = snapshot(state, CONFIG)
    return (
        value.steering_mode,
        value.manual_assistance_level,
        value.maximum_assistance_active,
    )


def test_initial_snapshot_and_effects() -> None:
    state = ApplicationState()

    assert snapshot(state, CONFIG) == ApplicationSnapshot(
        vehicle_speed_kph=0.0,
        steering_mode=SteeringMode.AUTO,
        manual_assistance_level=0,
        maximum_assistance_active=False,
        speed_valid=False,
        engine=EngineTelemetrySnapshot(
            rpm=EngineTelemetryValue(None, EngineTelemetryStatus.NEVER_OBSERVED),
            oil_temperature_c=EngineTelemetryValue(
                None,
                EngineTelemetryStatus.NEVER_OBSERVED,
            ),
            coolant_temperature_c=EngineTelemetryValue(
                None,
                EngineTelemetryStatus.NEVER_OBSERVED,
            ),
        ),
        active_steering_curve=ACTIVE_CURVE,
        steering_curve_activation_status=SteeringCurveActivationStatus.ACTIVE,
        button_pad_program=static_button_pad_program(AUTO_LEDS.rgb),
        high_beam_enabled=False,
        high_beam_strobe_active=False,
        high_beam_strobe_cycles_remaining=0,
        high_beam_next_transition_at=None,
    )
    assert initial_effects(state, CONFIG) == (
        static_effect(AUTO_LEDS),
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
    )


def test_button_fifteen_toggles_the_bounded_breathe_demo() -> None:
    started = controller.transition(
        ApplicationState(),
        ButtonPressed(button_index=15, observed_at=1.0),
        CONFIG,
        ACTIVE_CURVE.definition,
    )

    assert started.state.button_pad_demo_breathe_enabled
    assert started.effects == (SetButtonPadBreathe(15, True),)

    stopped = controller.transition(
        started.state,
        ButtonPressed(button_index=15, observed_at=2.0),
        CONFIG,
        ACTIVE_CURVE.definition,
    )

    assert not stopped.state.button_pad_demo_breathe_enabled
    assert stopped.effects == (SetButtonPadBreathe(15, False),)


def test_high_beam_button_starts_one_shot_strobe_and_ignores_repeated_presses() -> None:
    config = HighBeamStrobeConfig(
        cycle_count=2, asserted_duration_s=0.08, deasserted_duration_s=0.1
    )
    state = ApplicationState()

    started = controller.transition(
        state,
        ButtonPressed(4, 12.0),
        CONFIG,
        CURVE_DEFINITION,
        config,
    )

    assert started.state.high_beam_enabled is True
    assert started.state.high_beam_strobe_cycles_remaining == 2
    assert started.state.high_beam_next_transition_at == pytest.approx(12.08)
    assert started.effects == (SetHighBeam(True),)
    assert snapshot(started.state, CONFIG).high_beam_strobe_active is True

    repeated = controller.transition(
        started.state,
        ButtonPressed(4, 12.01),
        CONFIG,
        CURVE_DEFINITION,
        config,
    )
    assert repeated.state is started.state
    assert repeated.effects == ()


def test_high_beam_strobe_advances_on_its_own_deadlines_and_completes_deasserted() -> None:
    config = HighBeamStrobeConfig(
        cycle_count=2, asserted_duration_s=0.08, deasserted_duration_s=0.1
    )
    state = controller.transition(
        ApplicationState(), ButtonPressed(4, 12.0), CONFIG, CURVE_DEFINITION, config
    ).state

    early = controller.transition(
        state, HighBeamStrobeDeadlineReached(12.079), CONFIG, CURVE_DEFINITION, config
    )
    assert early.state is state
    assert early.effects == ()

    deasserted = controller.transition(
        state, HighBeamStrobeDeadlineReached(12.08), CONFIG, CURVE_DEFINITION, config
    )
    assert deasserted.state.high_beam_enabled is False
    assert deasserted.state.high_beam_strobe_cycles_remaining == 2
    assert deasserted.state.high_beam_next_transition_at == pytest.approx(12.18)
    assert deasserted.effects == (SetHighBeam(False),)

    reasserted = controller.transition(
        deasserted.state,
        HighBeamStrobeDeadlineReached(12.18),
        CONFIG,
        CURVE_DEFINITION,
        config,
    )
    assert reasserted.state.high_beam_enabled is True
    assert reasserted.state.high_beam_strobe_cycles_remaining == 1
    assert reasserted.effects == (SetHighBeam(True),)

    second_deasserted = controller.transition(
        reasserted.state,
        HighBeamStrobeDeadlineReached(12.26),
        CONFIG,
        CURVE_DEFINITION,
        config,
    )
    completed = controller.transition(
        second_deasserted.state,
        HighBeamStrobeDeadlineReached(12.36),
        CONFIG,
        CURVE_DEFINITION,
        config,
    )
    assert completed.state.high_beam_enabled is False
    assert completed.state.high_beam_strobe_cycles_remaining == 0
    assert completed.state.high_beam_next_transition_at is None
    assert completed.effects == ()


@pytest.mark.parametrize(
    ("initial_mode", "button_index", "expected", "expected_led_state"),
    [
        (SteeringMode.AUTO, 0, (SteeringMode.MANUAL, 0, False), MANUAL_LEDS),
        (SteeringMode.AUTO, 1, (SteeringMode.MANUAL, 0, False), MANUAL_LEDS),
        (SteeringMode.AUTO, 2, (SteeringMode.MANUAL, 0, False), MANUAL_LEDS),
        (
            SteeringMode.AUTO,
            3,
            (SteeringMode.MANUAL, 7, True),
            MANUAL_MAXIMUM_LEDS,
        ),
        (SteeringMode.MANUAL, 0, (SteeringMode.AUTO, 0, False), AUTO_LEDS),
        (SteeringMode.MANUAL, 1, (SteeringMode.MANUAL, 0, False), None),
        (SteeringMode.MANUAL, 2, (SteeringMode.MANUAL, 1, False), None),
        (
            SteeringMode.MANUAL,
            3,
            (SteeringMode.MANUAL, 7, True),
            MANUAL_MAXIMUM_LEDS,
        ),
    ],
)
def test_mapped_buttons_from_normal_modes(
    initial_mode: SteeringMode,
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    expected_led_state: ButtonLedState | None,
) -> None:
    state = application_state(mode=initial_mode)

    result = transition(state, ButtonPressed(button_index), CONFIG)

    assert projection(result.state) == expected
    expected_effects: tuple[ApplicationEffect, ...] = ()
    if expected_led_state is not None:
        expected_effects += (static_effect(expected_led_state),)
    if result.state.steering != state.steering:
        expected_effects += (controller._steering_command(result.state, CONFIG, CURVE_DEFINITION),)
    assert result.effects == expected_effects


@pytest.mark.parametrize(
    ("button_index", "expected", "expected_led_state"),
    [
        (0, (SteeringMode.AUTO, 3, False), AUTO_LEDS),
        (1, (SteeringMode.MANUAL, 3, False), MANUAL_LEDS),
        (2, (SteeringMode.MANUAL, 3, False), MANUAL_LEDS),
        (3, (SteeringMode.AUTO, 3, False), AUTO_LEDS),
    ],
)
def test_mapped_buttons_while_maximum_assistance_is_active(
    button_index: int,
    expected: tuple[SteeringMode, int, bool],
    expected_led_state: ButtonLedState | None,
) -> None:
    state = ApplicationState(MaximumAssistance(NormalSteering(manual_level=3)))

    result = transition(state, ButtonPressed(button_index), CONFIG)

    assert projection(result.state) == expected
    expected_effects: tuple[ApplicationEffect, ...] = ()
    if expected_led_state is not None:
        expected_effects += (static_effect(expected_led_state),)
    if result.state.steering != state.steering:
        expected_effects += (controller._steering_command(result.state, CONFIG, CURVE_DEFINITION),)
    assert result.effects == expected_effects


def test_mode_button_selects_auto_from_maximum_over_previous_manual_state() -> None:
    state = ApplicationState(MaximumAssistance(NormalSteering(SteeringMode.MANUAL, manual_level=5)))

    result = transition(state, ButtonPressed(0), CONFIG)

    assert projection(result.state) == (SteeringMode.AUTO, 5, False)
    assert result.effects == (
        static_effect(AUTO_LEDS),
        SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
    )


def test_maximum_assistance_restores_previous_manual_state() -> None:
    state = application_state(SteeringMode.MANUAL, 5)

    enabled = transition(state, ButtonPressed(3), CONFIG).state
    restored = transition(enabled, ButtonPressed(3), CONFIG).state

    assert projection(restored) == (SteeringMode.MANUAL, 5, False)


def test_first_assistance_press_after_maximum_only_restores_level() -> None:
    state = ApplicationState(MaximumAssistance(NormalSteering(manual_level=3)))

    restored = transition(state, ButtonPressed(2), CONFIG).state
    adjusted = transition(restored, ButtonPressed(2), CONFIG).state

    assert snapshot(restored, CONFIG).manual_assistance_level == 3
    assert snapshot(adjusted, CONFIG).manual_assistance_level == 4


def test_each_assistance_button_press_immediately_emits_its_new_command() -> None:
    state = application_state(SteeringMode.MANUAL, 5)

    raised = transition(state, ButtonPressed(2), CONFIG)
    lowered = transition(raised.state, ButtonPressed(1), CONFIG)

    assert raised.effects == (SetSteeringAssistance(6 / 7, SteeringCommandReason.MANUAL),)
    assert lowered.effects == (SetSteeringAssistance(5 / 7, SteeringCommandReason.MANUAL),)


def test_unknown_button_double_blinks_red_and_returns_to_its_displayed_colour() -> None:
    state = ApplicationState()

    result = transition(state, ButtonPressed(9, observed_at=2.0), CONFIG)

    assert result.state.button_feedback_deadlines[9] == pytest.approx(2.4)
    assert result.effects == (TriggerButtonPadBlink(9),)


def test_manual_assistance_is_clamped_to_configured_bounds() -> None:
    config = SteeringConfig(manual_level_count=3)
    state = normalize_state(application_state(SteeringMode.MANUAL, -4), config)

    state = transition(state, ButtonPressed(1), config).state
    for _ in range(4):
        state = transition(state, ButtonPressed(2), config).state

    assert snapshot(state, config).manual_assistance_level == 2


@pytest.mark.parametrize(
    ("evaluation_time", "expected_valid"),
    [(10.5, True), (11.0, True), (11.000_001, False)],
)
def test_speed_validity_is_derived_from_sample_age(
    evaluation_time: float,
    expected_valid: bool,
) -> None:
    observed = SpeedObserved(SpeedSample(42.5, 10.0, CanNetwork.FCAN))
    state = transition(ApplicationState(), observed, CONFIG).state

    state = transition(state, ControlTimerElapsed(evaluation_time), CONFIG).state

    value = snapshot(state, CONFIG)
    assert value.vehicle_speed_kph == 42.5
    assert value.speed_valid is expected_valid


def test_regressing_timer_cannot_make_stale_speed_valid() -> None:
    state = transition(
        ApplicationState(),
        SpeedObserved(SpeedSample(42.5, 1.0, CanNetwork.FCAN)),
        CONFIG,
    ).state
    stale = transition(state, ControlTimerElapsed(5.0), CONFIG).state

    result = transition(stale, ControlTimerElapsed(1.5), CONFIG)

    assert result.state.speed_evaluated_at == 5.0
    assert snapshot(result.state, CONFIG).speed_valid is False
    assert result.effects == (SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_STALE),)


def test_speed_sample_clamps_negative_speed_and_retains_observation() -> None:
    sample = SpeedSample(-2.0, 12.5, CanNetwork.PTCAN)

    result = transition(ApplicationState(), SpeedObserved(sample), CONFIG)

    assert result.state.speed_sample == SpeedSample(0.0, 12.5, CanNetwork.PTCAN)
    assert snapshot(result.state, CONFIG).speed_valid is True
    assert result.effects == ()


def test_zero_speed_start_immediately_uses_the_active_auto_curve() -> None:
    curve = replace(
        CURVE_DEFINITION,
        points=(
            replace(CURVE_DEFINITION.points[0], assistance_per_mille=950),
            *CURVE_DEFINITION.points[1:],
        ),
    )
    result = controller.transition(
        ApplicationState(),
        SpeedObserved(SpeedSample(0.0, 1.0, CanNetwork.FCAN)),
        CONFIG,
        curve,
    )

    assert result.effects == (SetSteeringAssistance(0.95, SteeringCommandReason.AUTO),)


def test_engine_observations_store_canonical_value_time_and_ptcan_source() -> None:
    events = (
        EngineRpmObserved(EngineRpmSample(3500, 10.0, CanNetwork.PTCAN)),
        OilTemperatureObserved(OilTemperatureSample(112.5, 10.1, CanNetwork.PTCAN)),
        CoolantTemperatureObserved(CoolantTemperatureSample(98.2, 10.2, CanNetwork.PTCAN)),
    )

    state = ApplicationState()
    for event in events:
        state = transition(state, event, CONFIG).state

    assert state.engine_rpm_sample == events[0].sample
    assert state.oil_temperature_sample == events[1].sample
    assert state.coolant_temperature_sample == events[2].sample


def test_engine_telemetry_ages_independently_with_monotonic_evaluation_time() -> None:
    state = transition(
        ApplicationState(),
        EngineRpmObserved(EngineRpmSample(3500, 10.0, CanNetwork.PTCAN)),
        CONFIG,
    ).state
    state = transition(
        state,
        OilTemperatureObserved(OilTemperatureSample(112.5, 10.5, CanNetwork.PTCAN)),
        CONFIG,
    ).state
    at_boundary = transition(state, ControlTimerElapsed(11.0), CONFIG).state

    boundary = snapshot(at_boundary, CONFIG).engine
    assert boundary.rpm == EngineTelemetryValue(3500, EngineTelemetryStatus.VALID)
    assert boundary.oil_temperature_c == EngineTelemetryValue(
        112.5,
        EngineTelemetryStatus.VALID,
    )
    assert boundary.coolant_temperature_c == EngineTelemetryValue(
        None,
        EngineTelemetryStatus.NEVER_OBSERVED,
    )

    stale_rpm = transition(at_boundary, ControlTimerElapsed(11.000_001), CONFIG).state
    regressed = transition(stale_rpm, ControlTimerElapsed(10.75), CONFIG).state
    projection = snapshot(regressed, CONFIG).engine

    assert regressed.engine_telemetry_evaluated_at == 11.000_001
    assert projection.rpm == EngineTelemetryValue(None, EngineTelemetryStatus.STALE)
    assert projection.oil_temperature_c.status is EngineTelemetryStatus.VALID
    assert projection.coolant_temperature_c.value is None


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            ApplicationState(),
            SetSteeringAssistance(0.0, SteeringCommandReason.SPEED_NEVER_OBSERVED),
        ),
        (
            application_state(SteeringMode.MANUAL, 4),
            SetSteeringAssistance(4 / 7, SteeringCommandReason.MANUAL),
        ),
        (
            ApplicationState(MaximumAssistance(NormalSteering())),
            SetSteeringAssistance(1.0, SteeringCommandReason.MAXIMUM),
        ),
    ],
)
def test_control_timer_selects_bounded_steering_command(
    state: ApplicationState,
    expected: SetSteeringAssistance,
) -> None:
    result = transition(state, ControlTimerElapsed(1.0), CONFIG)

    assert result.effects == (expected,)


def test_fresh_speed_selects_interpolated_auto_assistance() -> None:
    state = transition(
        ApplicationState(),
        SpeedObserved(SpeedSample(15.0, 1.0, CanNetwork.FCAN)),
        CONFIG,
    ).state

    result = transition(state, ControlTimerElapsed(1.5), CONFIG)

    assert len(result.effects) == 1
    command = result.effects[0]
    assert isinstance(command, SetSteeringAssistance)
    assert command.assistance == pytest.approx(
        5 / 6,
        abs=ASSISTANCE_QUANTIZATION_TOLERANCE,
    )
    assert command.reason is SteeringCommandReason.AUTO


@pytest.mark.parametrize(
    ("reason", "command_reason"),
    [
        (
            SteeringFallbackReason.CAN_READER_FAILURE,
            SteeringCommandReason.CAN_READER_FAILURE,
        ),
        (
            SteeringFallbackReason.INBOX_OVERFLOW,
            SteeringCommandReason.INBOX_OVERFLOW,
        ),
        (SteeringFallbackReason.SHUTDOWN, SteeringCommandReason.SHUTDOWN),
    ],
)
def test_fallback_inputs_select_zero_assistance(
    reason: SteeringFallbackReason,
    command_reason: SteeringCommandReason,
) -> None:
    result = transition(
        application_state(SteeringMode.MANUAL, 7),
        SteeringFallbackRequested(reason),
        CONFIG,
    )

    assert result.effects == (SetSteeringAssistance(0.0, command_reason),)


def test_transition_is_deterministic_and_does_not_mutate_input() -> None:
    state = ApplicationState()
    event = ButtonPressed(0)

    first = transition(state, event, CONFIG)
    second = transition(state, event, CONFIG)

    assert first == second
    assert first.state is not state
    assert projection(state) == (SteeringMode.AUTO, 0, False)
    with pytest.raises(FrozenInstanceError):
        state.speed_evaluated_at = 1.0  # type: ignore[misc]
