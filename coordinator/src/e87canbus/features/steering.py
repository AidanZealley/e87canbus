"""Pure steering-assistance calculations."""

from collections.abc import Sequence

SpeedAssistanceCurve = Sequence[tuple[float, float]]


def clamp_manual_level(level: int, level_count: int) -> int:
    if level_count < 1:
        raise ValueError("level_count must be at least 1")
    return min(max(level, 0), level_count - 1)


def interpolate_speed_to_assistance(
    speed_kph: float,
    curve: SpeedAssistanceCurve,
) -> float:
    if not curve:
        raise ValueError("curve must contain at least one point")
    points = sorted(curve, key=lambda point: point[0])

    if speed_kph <= points[0][0]:
        return points[0][1]
    if speed_kph >= points[-1][0]:
        return points[-1][1]

    for (left_speed, left_assistance), (right_speed, right_assistance) in zip(
        points,
        points[1:],
        strict=False,
    ):
        if left_speed <= speed_kph <= right_speed:
            span = right_speed - left_speed
            if span == 0:
                return right_assistance
            ratio = (speed_kph - left_speed) / span
            return left_assistance + ratio * (right_assistance - left_assistance)

    return points[-1][1]
