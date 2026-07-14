import pytest
from e87canbus.features.steering import (
    ASSISTANCE_QUANTIZATION_TOLERANCE,
    clamp_manual_level,
    default_steering_curve_definition,
    interpolate_steering_curve_definition,
)


def test_assistance_curve_interpolation() -> None:
    curve = default_steering_curve_definition()

    assert interpolate_steering_curve_definition(15.0, curve) == pytest.approx(
        5.0 / 6.0,
        abs=ASSISTANCE_QUANTIZATION_TOLERANCE,
    )


def test_speed_values_clamp_to_curve_bounds() -> None:
    curve = default_steering_curve_definition()

    assert interpolate_steering_curve_definition(-10.0, curve) == 1.0
    assert interpolate_steering_curve_definition(200.0, curve) == 0.0


def test_manual_level_clamping() -> None:
    assert clamp_manual_level(-1, 8) == 0
    assert clamp_manual_level(3, 8) == 3
    assert clamp_manual_level(99, 8) == 7
