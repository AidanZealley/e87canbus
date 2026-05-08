import pytest
from e87canbus.config import default_config
from e87canbus.steering_control import (
    clamp_manual_level,
    interpolate_speed_to_current,
    target_current_to_normalized_command,
)


def test_assistance_curve_interpolation() -> None:
    curve = default_config().steering.auto_assistance_curve

    assert interpolate_speed_to_current(15.0, curve) == pytest.approx(700.0)


def test_speed_values_clamp_to_curve_bounds() -> None:
    curve = default_config().steering.auto_assistance_curve

    assert interpolate_speed_to_current(-10.0, curve) == 800.0
    assert interpolate_speed_to_current(200.0, curve) == 200.0


def test_manual_level_clamping() -> None:
    assert clamp_manual_level(-1, 8) == 0
    assert clamp_manual_level(3, 8) == 3
    assert clamp_manual_level(99, 8) == 7


def test_target_current_to_normalized_command() -> None:
    assert target_current_to_normalized_command(200, 200, 800) == 0.0
    assert target_current_to_normalized_command(500, 200, 800) == pytest.approx(0.5)
    assert target_current_to_normalized_command(800, 200, 800) == 1.0

