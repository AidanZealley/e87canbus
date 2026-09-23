from dataclasses import FrozenInstanceError

import pytest
from e87canbus.config import CanNetwork, EngineTelemetryConfig, SteeringConfig
from e87canbus.domain.controller import (
    EngineTelemetryStatus,
    EngineTelemetryValue,
    snapshot,
    transition,
)
from e87canbus.domain.events import ControlTimerElapsed, EngineRpmObserved, SpeedObserved
from e87canbus.domain.state import (
    ApplicationState,
    EngineRpmSample,
    MaximumAssistance,
    NormalSteering,
    SpeedSample,
    SteeringMode,
)
from e87canbus.domain.steering.curves import initial_active_steering_curve

CONFIG = SteeringConfig()
ENGINE_CONFIG = EngineTelemetryConfig()
ACTIVE_CURVE = initial_active_steering_curve()


def projection(state: ApplicationState):
    return snapshot(state, CONFIG, ENGINE_CONFIG, ACTIVE_CURVE, "built-in", None)


@pytest.mark.parametrize(("at", "valid"), [(10.5, True), (11.0, True), (11.000001, False)])
def test_speed_is_browser_telemetry_with_freshness(at: float, valid: bool) -> None:
    state = transition(
        ApplicationState(), SpeedObserved(SpeedSample(42.5, 10.0, CanNetwork.FCAN))
    ).state
    state = transition(state, ControlTimerElapsed(at)).state
    assert projection(state).vehicle_speed_kph == 42.5
    assert projection(state).speed_valid is valid
    assert not hasattr(transition(state, ControlTimerElapsed(at)), "effects")


def test_regressing_timer_cannot_restore_stale_speed() -> None:
    state = transition(
        ApplicationState(), SpeedObserved(SpeedSample(42.5, 1.0, CanNetwork.FCAN))
    ).state
    state = transition(state, ControlTimerElapsed(5.0)).state
    state = transition(state, ControlTimerElapsed(1.5)).state
    assert state.speed_evaluated_at == 5.0
    assert not projection(state).speed_valid


def test_speed_sample_clamps_negative_speed_and_retains_observation() -> None:
    state = transition(
        ApplicationState(), SpeedObserved(SpeedSample(-2.0, 12.5, CanNetwork.PTCAN))
    ).state
    assert state.speed_sample == SpeedSample(0.0, 12.5, CanNetwork.PTCAN)


def test_engine_telemetry_ages_independently() -> None:
    state = transition(
        ApplicationState(), EngineRpmObserved(EngineRpmSample(3500, 10.0, CanNetwork.PTCAN))
    ).state
    assert projection(state).engine.rpm == EngineTelemetryValue(3500, EngineTelemetryStatus.VALID)
    state = transition(state, ControlTimerElapsed(11.000001)).state
    assert projection(state).engine.rpm == EngineTelemetryValue(None, EngineTelemetryStatus.STALE)


def test_snapshot_projects_desired_steering_without_applied_state() -> None:
    state = ApplicationState(steering=MaximumAssistance(NormalSteering(SteeringMode.AUTO, 4)))
    projected = projection(state)
    assert projected.maximum_assistance_active
    assert projected.manual_assistance_level == 4
    assert not hasattr(projected, "servotronic")
    with pytest.raises(FrozenInstanceError):
        projected.vehicle_speed_kph = 20  # type: ignore[misc]


def test_transition_does_not_mutate_input() -> None:
    state = ApplicationState()
    changed = transition(state, SpeedObserved(SpeedSample(30.0, 2.0, CanNetwork.FCAN)))
    assert state.speed_sample is None
    assert changed.state != state
