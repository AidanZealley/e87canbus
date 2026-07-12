"""Pure steering-assistance calculations."""

from collections.abc import Sequence

SpeedCurrentCurve = Sequence[tuple[float, float]]


def clamp_manual_level(level: int, level_count: int) -> int:
    if level_count < 1:
        raise ValueError("level_count must be at least 1")
    return min(max(level, 0), level_count - 1)


def interpolate_speed_to_current(speed_kph: float, curve: SpeedCurrentCurve) -> float:
    if not curve:
        raise ValueError("curve must contain at least one point")
    points = sorted(curve, key=lambda point: point[0])

    if speed_kph <= points[0][0]:
        return points[0][1]
    if speed_kph >= points[-1][0]:
        return points[-1][1]

    for (left_speed, left_current), (right_speed, right_current) in zip(
        points,
        points[1:],
        strict=False,
    ):
        if left_speed <= speed_kph <= right_speed:
            span = right_speed - left_speed
            if span == 0:
                return right_current
            ratio = (speed_kph - left_speed) / span
            return left_current + ratio * (right_current - left_current)

    return points[-1][1]


def target_current_to_normalized_command(
    target_current_ma: float,
    min_current_ma: float,
    max_current_ma: float,
) -> float:
    if max_current_ma <= min_current_ma:
        raise ValueError("max_current_ma must be greater than min_current_ma")
    clamped = min(max(target_current_ma, min_current_ma), max_current_ma)
    return (clamped - min_current_ma) / (max_current_ma - min_current_ma)


class PwmSteeringDriver:
    """Future adapter boundary for pigpio or another PWM/current backend."""

    def set_normalized_command(self, command: float) -> None:
        raise NotImplementedError("PWM steering output is out of scope for the initial scaffold")
