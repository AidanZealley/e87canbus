import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from e87canbus.features.steering import (
    BUILT_IN_STEERING_CURVE,
    STEERING_CURVE_CONFORMANCE_TOLERANCE,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    interpolate_monotone_cubic_v1,
    interpolate_steering_curve_definition,
)

VECTOR_PATH = Path(__file__).parents[2] / "docs" / "assist-curve" / "monotone-cubic-v1-vectors.json"


def _definition(values: list[int]) -> SteeringCurveDefinition:
    return SteeringCurveDefinition(
        schema_version=1,
        points=tuple(
            SteeringCurvePoint(point.speed_deci_kph, assistance)
            for point, assistance in zip(BUILT_IN_STEERING_CURVE.points, values, strict=True)
        ),
    )


def _load_vectors() -> dict[str, Any]:
    with VECTOR_PATH.open(encoding="utf-8") as vector_file:
        return json.load(vector_file)


def test_monotone_cubic_matches_checked_in_language_neutral_vectors() -> None:
    vectors = _load_vectors()

    assert vectors["algorithm"] == "monotone-cubic-v1"
    assert vectors["schema_version"] == 1
    assert vectors["floating_point"] == "IEEE 754 binary64"
    assert vectors["absolute_tolerance"] == STEERING_CURVE_CONFORMANCE_TOLERANCE
    for case in vectors["cases"]:
        definition = _definition(case["assistance_per_mille"])
        for speed_deci_kph, expected in case["evaluations"]:
            actual = interpolate_steering_curve_definition(speed_deci_kph / 10.0, definition)
            assert actual == pytest.approx(
                expected,
                abs=STEERING_CURVE_CONFORMANCE_TOLERANCE,
            ), f"{case['name']} at {speed_deci_kph} deci-km/h"


@pytest.mark.parametrize(
    "values",
    [
        [500] * 8,
        [1000, 1000, 1000, 1000, 0, 0, 0, 0],
        [1000, 800, 800, 500, 500, 200, 200, 0],
        [1000, 889, 778, 667, 381, 0, 0, 0],
        [8, 7, 6, 5, 4, 3, 2, 1],
        *([1000] * (index + 1) + [0] * (7 - index) for index in range(7)),
        *(
            [8 - min(point_index, transition_index) for point_index in range(8)]
            for transition_index in range(1, 8)
        ),
    ],
)
def test_monotone_cubic_is_bounded_non_increasing_and_has_no_segment_overshoot(
    values: list[int],
) -> None:
    definition = _definition(values)
    samples = [
        interpolate_steering_curve_definition(speed / 10.0, definition)
        for speed in range(-10, 2511)
    ]

    assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in samples)
    assert all(
        left + STEERING_CURVE_CONFORMANCE_TOLERANCE >= right
        for left, right in zip(samples, samples[1:], strict=False)
    )
    for point in definition.points:
        assert (
            interpolate_steering_curve_definition(point.speed_deci_kph / 10.0, definition)
            == point.assistance_per_mille / 1000.0
        )
    for left, right in zip(definition.points, definition.points[1:], strict=False):
        segment = [
            interpolate_steering_curve_definition(speed / 10.0, definition)
            for speed in range(left.speed_deci_kph, right.speed_deci_kph + 1)
        ]
        assert (
            min(segment) + STEERING_CURVE_CONFORMANCE_TOLERANCE
            >= right.assistance_per_mille / 1000.0
        )
        assert (
            max(segment) - STEERING_CURVE_CONFORMANCE_TOLERANCE
            <= left.assistance_per_mille / 1000.0
        )


def test_monotone_cubic_holds_endpoints_and_rejects_non_finite_evaluation_speed() -> None:
    definition = replace(
        BUILT_IN_STEERING_CURVE,
    )

    assert interpolate_steering_curve_definition(-1.0, definition) == 1.0
    assert interpolate_steering_curve_definition(251.0, definition) == 0.0
    for speed in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="speed_kph must be finite"):
            interpolate_steering_curve_definition(speed, definition)


def test_two_point_monotone_cubic_contract_reduces_to_the_secant_line() -> None:
    points = (
        SteeringCurvePoint(30, 900),
        SteeringCurvePoint(770, 100),
    )

    assert interpolate_monotone_cubic_v1(30, points) == 0.9
    assert interpolate_monotone_cubic_v1(400, points) == pytest.approx(0.5)
    assert interpolate_monotone_cubic_v1(770, points) == 0.1


def test_monotone_cubic_defensive_seam_handles_highly_unequal_positive_spans() -> None:
    points = (
        SteeringCurvePoint(0, 1000),
        SteeringCurvePoint(1, 900),
        SteeringCurvePoint(1_000_001, 100),
        SteeringCurvePoint(1_000_002, 0),
    )
    evaluation_speeds = (
        0,
        0.5,
        1,
        10,
        100_001,
        500_001,
        900_001,
        1_000_001,
        1_000_001.5,
        1_000_002,
    )
    values = [interpolate_monotone_cubic_v1(speed, points) for speed in evaluation_speeds]

    assert all(math.isfinite(value) and 0.0 <= value <= 1.0 for value in values)
    assert all(
        left + STEERING_CURVE_CONFORMANCE_TOLERANCE >= right
        for left, right in zip(values, values[1:], strict=False)
    )
    for point in points:
        assert (
            interpolate_monotone_cubic_v1(point.speed_deci_kph, points)
            == point.assistance_per_mille / 1000.0
        )


@pytest.mark.parametrize(
    "points",
    [
        (SteeringCurvePoint(0, 1000), SteeringCurvePoint(0, 0)),
        (SteeringCurvePoint(1, 1000), SteeringCurvePoint(0, 0)),
    ],
)
def test_monotone_cubic_defensive_seam_rejects_non_positive_spans(
    points: tuple[SteeringCurvePoint, SteeringCurvePoint],
) -> None:
    with pytest.raises(ValueError, match="strictly increasing"):
        interpolate_monotone_cubic_v1(0, points)
