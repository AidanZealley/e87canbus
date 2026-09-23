from dataclasses import FrozenInstanceError, replace

import pytest
from e87canbus.config import (
    CanNetwork,
    EngineTelemetryConfig,
    SteeringConfig,
)
from e87canbus.domain import controller
from e87canbus.domain.controller import (
    ApplicationSnapshot,
    EngineTelemetryStatus,
    EngineTelemetryValue,
    Transition,
)
from e87canbus.domain.events import (
    ApplicationEffect,
    ApplicationEvent,
    ControlTimerElapsed,
    CoolantTemperatureObserved,
    EngineRpmObserved,
    OilTemperatureObserved,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
    SteeringFallbackReason,
    SteeringFallbackRequested,
)
from e87canbus.domain.state import (
    ApplicationState,
    CoolantTemperatureSample,
    EngineRpmSample,
    MaximumAssistance,
    NormalSteering,
    OilTemperatureSample,
    SpeedSample,
    SteeringMode,
)
from e87canbus.domain.steering.curves import (
    ASSISTANCE_QUANTIZATION_TOLERANCE,
    SteeringCurveActivationStatus,
    default_steering_curve_definition,
    initial_active_steering_curve,
)

CONFIG = SteeringConfig()
ENGINE_CONFIG = EngineTelemetryConfig()
ACTIVE_CURVE = initial_active_steering_curve()
CURVE_DEFINITION = default_steering_curve_definition()


def snapshot(state: ApplicationState, config: SteeringConfig) -> ApplicationSnapshot:
    return controller.snapshot(
        state,
        config,
        ENGINE_CONFIG,
        ACTIVE_CURVE,
        SteeringCurveActivationStatus.ACTIVE,
        "built-in",
        None,
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
            SetSteeringAssistance(0.4, SteeringCommandReason.MANUAL),
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
    event = SpeedObserved(SpeedSample(10.0, 1.0, CanNetwork.FCAN))

    first = transition(state, event, CONFIG)
    second = transition(state, event, CONFIG)

    assert first == second
    assert first.state is not state
    assert projection(state) == (SteeringMode.AUTO, 0, False)
    with pytest.raises(FrozenInstanceError):
        state.speed_evaluated_at = 1.0  # type: ignore[misc]
