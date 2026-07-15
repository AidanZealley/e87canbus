from dataclasses import replace

import pytest
from e87canbus.application.events import SetSteeringAssistance, SteeringCommandReason
from e87canbus.application.state import (
    ApplicationState,
    MaximumAssistance,
    NormalSteering,
    SpeedSample,
    SteeringMode,
)
from e87canbus.config import CanNetwork
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    CurveInterpolation,
    SteeringCurveActivationStatus,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    initial_active_steering_curve,
    interpolate_steering_curve_definition,
    steering_curve_fingerprint,
)
from e87canbus.runtime import (
    ActivateSteeringCurve,
    CoordinatorKernel,
    KernelStarted,
    ReceivedCanFrame,
    StateTopic,
    SteeringActuatorFailed,
    TimerElapsed,
    UnsupportedSteeringCurveInterpolation,
)
from e87canbus.simulation.engine import (
    ActivateCurve,
    RunControlTimer,
    SetVehicleSpeed,
    SimulationEngine,
    snapshot_to_dict,
)
from e87canbus.simulation.protocol import SimulationProtocolRouter, encode_simulated_speed

SAVED_PROFILE_ID = "11111111-1111-4111-8111-111111111111"


def constant_curve(assistance_per_mille: int) -> SteeringCurveDefinition:
    return replace(
        BUILT_IN_STEERING_CURVE,
        points=tuple(
            SteeringCurvePoint(point.speed_deci_kph, assistance_per_mille)
            for point in BUILT_IN_STEERING_CURVE.points
        ),
    )


def started_kernel(
    *,
    state: ApplicationState | None = None,
    active_curve=None,
) -> CoordinatorKernel:
    kernel = CoordinatorKernel(state=state, active_steering_curve=active_curve)
    assert kernel.dispatch(KernelStarted(0.0)) is not None
    return kernel


def test_builtin_definition_is_active_on_ordinary_startup() -> None:
    kernel = started_kernel()

    active = kernel.snapshot().active_steering_curve
    assert active.definition == BUILT_IN_STEERING_CURVE
    assert active.fingerprint == steering_curve_fingerprint(BUILT_IN_STEERING_CURVE)
    assert active.activation_revision == 1
    assert active.saved_profile_id is None
    assert kernel.snapshot().steering_curve_activation_status is (
        SteeringCurveActivationStatus.ACTIVE
    )


def test_activation_recalculates_fresh_auto_output_immediately() -> None:
    state = ApplicationState(
        speed_sample=SpeedSample(50.0, 1.0, CanNetwork.FCAN),
        speed_evaluated_at=1.0,
    )
    kernel = started_kernel(state=state)

    commit = kernel.dispatch(ActivateSteeringCurve(constant_curve(500), requested_at=1.0))

    assert commit is not None
    assert commit.revision == 2
    assert commit.changed_topics == {StateTopic.STEERING}
    assert commit.snapshot.active_steering_curve.activation_revision == 2
    assert commit.effects == (SetSteeringAssistance(0.5, SteeringCommandReason.AUTO),)
    timer = kernel.dispatch(TimerElapsed(1.1))
    assert timer is not None
    assert timer.effects == commit.effects


def test_simulator_activation_applies_smooth_output_at_an_intermediate_speed() -> None:
    engine = SimulationEngine()
    smooth = replace(
        BUILT_IN_STEERING_CURVE,
        interpolation=CurveInterpolation.MONOTONE_CUBIC_V1,
    )
    speed_kph = 45.0
    expected = interpolate_steering_curve_definition(speed_kph, smooth)

    engine.execute(SetVehicleSpeed(speed_kph))
    engine.execute(RunControlTimer(1.0))
    result = engine.execute(ActivateCurve(smooth))
    serialized = snapshot_to_dict(result.snapshot, include_trace=False)

    assert result.snapshot.steering_controller.effective_assistance == pytest.approx(expected)
    assert result.snapshot.steering_controller.last_command_reason is SteeringCommandReason.AUTO
    assert result.snapshot.application.active_steering_curve.definition == smooth
    assert serialized["steering_controller"]["effective_assistance"] == pytest.approx(expected)
    assert (
        serialized["application"]["active_steering_curve"]["definition"]["interpolation"]
        == "monotone-cubic-v1"
    )


@pytest.mark.parametrize(
    "steering",
    [
        NormalSteering(SteeringMode.MANUAL, 3),
        MaximumAssistance(NormalSteering(SteeringMode.AUTO, 2)),
    ],
)
def test_activation_preserves_manual_and_maximum_modes_without_output(steering) -> None:
    state = ApplicationState(
        steering=steering,
        speed_sample=SpeedSample(50.0, 1.0, CanNetwork.FCAN),
        speed_evaluated_at=1.0,
    )
    kernel = started_kernel(state=state)

    commit = kernel.dispatch(ActivateSteeringCurve(constant_curve(500), requested_at=1.0))

    assert commit is not None
    assert kernel.state.steering == steering
    assert commit.effects == ()


def test_identical_activation_is_idempotent_but_can_publish_saved_provenance() -> None:
    kernel = started_kernel()

    commit = kernel.dispatch(
        ActivateSteeringCurve(
            BUILT_IN_STEERING_CURVE,
            SAVED_PROFILE_ID,
            7,
            requested_at=1.0,
        )
    )

    assert commit is not None
    assert commit.revision == 2
    assert commit.snapshot.active_steering_curve.activation_revision == 1
    assert commit.snapshot.active_steering_curve.saved_profile_id == SAVED_PROFILE_ID
    assert commit.snapshot.active_steering_curve.saved_profile_revision == 7
    assert commit.effects == ()
    repeated = kernel.dispatch(
        ActivateSteeringCurve(
            BUILT_IN_STEERING_CURVE,
            SAVED_PROFILE_ID,
            7,
            requested_at=2.0,
        )
    )
    assert repeated is not None
    assert repeated.revision == 3
    assert repeated.state_changed is False
    assert repeated.effects == ()


def test_invalid_activation_leaves_active_state_and_revision_unchanged() -> None:
    kernel = started_kernel()
    invalid = replace(BUILT_IN_STEERING_CURVE)
    object.__setattr__(invalid, "schema_version", 99)
    before = kernel.snapshot()

    with pytest.raises(ValueError, match="unsupported.*schema_version"):
        kernel.dispatch(ActivateSteeringCurve(invalid, requested_at=1.0))

    assert kernel.snapshot() == before
    assert kernel.diagnostics().revision == 1


def test_consumer_capability_rejects_unsupported_interpolation_before_activation() -> None:
    kernel = CoordinatorKernel(
        supported_steering_curve_interpolations=(CurveInterpolation.LINEAR_V1,)
    )
    assert kernel.dispatch(KernelStarted(0.0)) is not None
    smooth = replace(
        BUILT_IN_STEERING_CURVE,
        interpolation=CurveInterpolation.MONOTONE_CUBIC_V1,
    )
    before = kernel.snapshot()

    with pytest.raises(UnsupportedSteeringCurveInterpolation) as caught:
        kernel.dispatch(ActivateSteeringCurve(smooth, requested_at=1.0))

    assert caught.value.interpolation is CurveInterpolation.MONOTONE_CUBIC_V1
    assert caught.value.supported_interpolations == (CurveInterpolation.LINEAR_V1,)
    assert kernel.snapshot() == before
    assert kernel.diagnostics().revision == 1


def test_invalid_saved_provenance_leaves_active_state_unchanged() -> None:
    kernel = started_kernel()
    before = kernel.snapshot()

    with pytest.raises(ValueError, match="supplied together"):
        kernel.dispatch(
            ActivateSteeringCurve(
                constant_curve(500),
                saved_profile_id=SAVED_PROFILE_ID,
                requested_at=1.0,
            )
        )

    assert kernel.snapshot() == before
    assert kernel.diagnostics().revision == 1


def test_activation_order_is_deterministic_relative_to_timer() -> None:
    first = CoordinatorKernel(router=SimulationProtocolRouter())
    second = CoordinatorKernel(router=SimulationProtocolRouter())
    inputs = (
        KernelStarted(0.0),
        ReceivedCanFrame(CanNetwork.FCAN, encode_simulated_speed(50.0), 1.0),
        ActivateSteeringCurve(constant_curve(500), requested_at=1.05),
        TimerElapsed(1.1),
    )

    first_commits = tuple(first.dispatch(item) for item in inputs)
    second_commits = tuple(second.dispatch(item) for item in inputs)

    assert first_commits == second_commits
    assert [commit.revision for commit in first_commits if commit is not None] == [1, 2, 3, 4]
    assert first_commits[2] is not None
    assert first_commits[2].effects == (
        SetSteeringAssistance(0.5, SteeringCommandReason.AUTO),
    )


def test_restart_discards_unsaved_activation_but_can_restore_selected_saved_curve() -> None:
    custom = constant_curve(500)
    running = started_kernel()
    assert running.dispatch(ActivateSteeringCurve(custom, requested_at=1.0)) is not None

    ordinary_restart = started_kernel()
    saved_restart = started_kernel(
        active_curve=initial_active_steering_curve(
            custom,
            saved_profile_id=SAVED_PROFILE_ID,
            saved_profile_revision=4,
        )
    )

    assert ordinary_restart.snapshot().active_steering_curve.definition == BUILT_IN_STEERING_CURVE
    assert saved_restart.snapshot().active_steering_curve.definition == custom
    assert saved_restart.snapshot().active_steering_curve.activation_revision == 1
    assert saved_restart.snapshot().active_steering_curve.saved_profile_revision == 4


def test_post_activation_output_failure_uses_existing_fatal_health_path() -> None:
    state = ApplicationState(
        speed_sample=SpeedSample(50.0, 1.0, CanNetwork.FCAN),
        speed_evaluated_at=1.0,
    )
    kernel = started_kernel(state=state)
    commit = kernel.dispatch(ActivateSteeringCurve(constant_curve(500), requested_at=1.0))
    assert commit is not None and commit.effects

    assert kernel.dispatch(SteeringActuatorFailed(1.1, "activation output failed")) is None

    assert kernel.health.fatal is True
    assert kernel.health.steering_actuator_fault is not None
    assert kernel.health.steering_actuator_fault.message == "activation output failed"


def test_serialized_snapshot_contains_complete_authoritative_active_projection() -> None:
    engine = SimulationEngine()
    custom = constant_curve(500)
    commit = engine.kernel.dispatch(
        ActivateSteeringCurve(custom, SAVED_PROFILE_ID, 4, requested_at=1.0)
    )
    assert commit is not None

    serialized = snapshot_to_dict(engine.snapshot(), include_trace=False)

    active = serialized["application"]["active_steering_curve"]
    assert active == {
        "definition": {
            "schema_version": 1,
            "interpolation": "linear-v1",
            "points": [
                {
                    "speed_deci_kph": point.speed_deci_kph,
                    "assistance_per_mille": 500,
                }
                for point in custom.points
            ],
        },
        "fingerprint": steering_curve_fingerprint(custom),
        "activation_revision": 2,
        "status": "active",
        "saved_profile_id": SAVED_PROFILE_ID,
        "saved_profile_revision": 4,
        "supported_interpolations": ["linear-v1", "monotone-cubic-v1"],
    }
