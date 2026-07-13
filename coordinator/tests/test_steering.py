import pytest
from e87canbus.config import default_config
from e87canbus.features.steering import (
    clamp_manual_level,
    interpolate_speed_to_assistance,
)


def test_assistance_curve_interpolation() -> None:
    curve = default_config().steering.auto_assistance_curve

    assert interpolate_speed_to_assistance(15.0, curve) == pytest.approx(5.0 / 6.0)


def test_speed_values_clamp_to_curve_bounds() -> None:
    curve = default_config().steering.auto_assistance_curve

    assert interpolate_speed_to_assistance(-10.0, curve) == 1.0
    assert interpolate_speed_to_assistance(200.0, curve) == 0.0


def test_manual_level_clamping() -> None:
    assert clamp_manual_level(-1, 8) == 0
    assert clamp_manual_level(3, 8) == 3
    assert clamp_manual_level(99, 8) == 7
