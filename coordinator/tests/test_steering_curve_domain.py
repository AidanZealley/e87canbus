from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from e87canbus.features.steering import (
    ASSISTANCE_QUANTIZATION_TOLERANCE,
    BUILT_IN_STEERING_CURVE,
    STEERING_CURVE_V1_SPEEDS_DECI_KPH,
    STEERING_PROFILE_NAME_MAX_LENGTH,
    CurveInterpolation,
    SteeringCurveDefinition,
    SteeringCurvePoint,
    StoredSteeringProfile,
    canonical_steering_curve_bytes,
    canonical_utc_timestamp,
    default_steering_curve_definition,
    interpolate_speed_to_assistance,
    interpolate_steering_curve_definition,
    steering_curve_as_float_pairs,
    steering_curve_fingerprint,
    validate_steering_curve_definition,
)

PROFILE_ID = "12345678-1234-5678-9234-567812345678"
CREATED_AT = "2026-07-14T10:30:00.000000Z"
UPDATED_AT = "2026-07-14T11:45:12.345678Z"


def _point_with(index: int, **changes: Any) -> tuple[SteeringCurvePoint, ...]:
    points = list(BUILT_IN_STEERING_CURVE.points)
    points[index] = replace(points[index], **changes)
    return tuple(points)


def _profile(**changes: Any) -> StoredSteeringProfile:
    values = {
        "profile_id": PROFILE_ID,
        "name": "Track",
        "revision": 1,
        "definition": BUILT_IN_STEERING_CURVE,
        "created_at": CREATED_AT,
        "updated_at": UPDATED_AT,
    }
    values.update(changes)
    return StoredSteeringProfile(**values)


def test_builtin_definition_is_the_documented_stable_default() -> None:
    definition = default_steering_curve_definition()

    validate_steering_curve_definition(definition)
    assert definition is BUILT_IN_STEERING_CURVE
    assert definition.schema_version == 1
    assert definition.interpolation is CurveInterpolation.LINEAR_V1
    assert tuple(point.speed_deci_kph for point in definition.points) == (
        STEERING_CURVE_V1_SPEEDS_DECI_KPH
    )
    assert tuple(point.assistance_per_mille for point in definition.points) == (
        1000,
        889,
        778,
        667,
        381,
        0,
        0,
        0,
    )


@pytest.mark.parametrize(
    ("make_definition", "message"),
    [
        (lambda: replace(BUILT_IN_STEERING_CURVE, schema_version=2), "unsupported.*schema"),
        (lambda: replace(BUILT_IN_STEERING_CURVE, schema_version=True), "must be an integer"),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                interpolation=CurveInterpolation.MONOTONE_CUBIC_V1,
            ),
            "unsupported.*interpolation",
        ),
        (
            lambda: replace(BUILT_IN_STEERING_CURVE, interpolation="linear-v1"),
            "CurveInterpolation",
        ),
        (lambda: replace(BUILT_IN_STEERING_CURVE, points=[]), "immutable tuple"),
        (lambda: replace(BUILT_IN_STEERING_CURVE, points=()), "requires 8 points"),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=(*BUILT_IN_STEERING_CURVE.points, BUILT_IN_STEERING_CURVE.points[-1]),
            ),
            "requires 8 points",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=(*BUILT_IN_STEERING_CURVE.points[:-1], (2500, 0)),
            ),
            "SteeringCurvePoint",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(0, speed_deci_kph=True),
            ),
            "speed_deci_kph must be an integer",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(0, speed_deci_kph=-1),
            ),
            "non-negative",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(1, speed_deci_kph=0),
            ),
            "strictly increasing",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(2, speed_deci_kph=50),
            ),
            "strictly increasing",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(1, speed_deci_kph=101),
            ),
            "exactly match",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(0, assistance_per_mille=True),
            ),
            "assistance_per_mille must be an integer",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(0, assistance_per_mille=-1),
            ),
            "between 0 and 1000",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(0, assistance_per_mille=1001),
            ),
            "between 0 and 1000",
        ),
        (
            lambda: replace(
                BUILT_IN_STEERING_CURVE,
                points=_point_with(7, assistance_per_mille=1),
            ),
            "non-increasing",
        ),
    ],
)
def test_invalid_definition_fields_fail_closed(make_definition: Any, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_definition()


def test_assistance_bounds_are_inclusive() -> None:
    definition = replace(
        BUILT_IN_STEERING_CURVE,
        points=tuple(
            replace(point, assistance_per_mille=1000 if index < 4 else 0)
            for index, point in enumerate(BUILT_IN_STEERING_CURVE.points)
        ),
    )

    validate_steering_curve_definition(definition)


def test_domain_values_are_immutable() -> None:
    profile = _profile()

    with pytest.raises(FrozenInstanceError):
        BUILT_IN_STEERING_CURVE.points[0].assistance_per_mille = 500  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        BUILT_IN_STEERING_CURVE.points = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        profile.revision = 2  # type: ignore[misc]


def test_canonical_bytes_and_fingerprint_are_stable() -> None:
    constructed_with_different_argument_order = SteeringCurveDefinition(
        points=tuple(
            SteeringCurvePoint(
                assistance_per_mille=point.assistance_per_mille,
                speed_deci_kph=point.speed_deci_kph,
            )
            for point in BUILT_IN_STEERING_CURVE.points
        ),
        interpolation=CurveInterpolation.LINEAR_V1,
        schema_version=1,
    )

    assert canonical_steering_curve_bytes(constructed_with_different_argument_order) == (
        b'{"interpolation":"linear-v1","points":['
        b'{"assistance_per_mille":1000,"speed_deci_kph":0},'
        b'{"assistance_per_mille":889,"speed_deci_kph":100},'
        b'{"assistance_per_mille":778,"speed_deci_kph":200},'
        b'{"assistance_per_mille":667,"speed_deci_kph":300},'
        b'{"assistance_per_mille":381,"speed_deci_kph":600},'
        b'{"assistance_per_mille":0,"speed_deci_kph":1000},'
        b'{"assistance_per_mille":0,"speed_deci_kph":1600},'
        b'{"assistance_per_mille":0,"speed_deci_kph":2500}],"schema_version":1}'
    )
    assert steering_curve_fingerprint(constructed_with_different_argument_order) == (
        "a71bc312fed723d3aed114c01acba33a97fb9a3f9025999a21da1b9697c70179"
    )


def test_stored_metadata_does_not_change_definition_fingerprint() -> None:
    original = _profile()
    changed_metadata = _profile(
        profile_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        name="Wet",
        revision=9,
        created_at="2026-07-01T00:00:00.000000Z",
        updated_at="2026-07-15T00:00:00.000000Z",
    )

    assert steering_curve_fingerprint(original.definition) == steering_curve_fingerprint(
        changed_metadata.definition
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"profile_id": 1}, "UUID text"),
        ({"profile_id": "not-a-uuid"}, "UUID"),
        ({"profile_id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"}, "canonical UUID"),
        ({"name": 1}, "name must be text"),
        ({"name": ""}, "non-empty and trimmed"),
        ({"name": " Track"}, "non-empty and trimmed"),
        ({"name": "x" * (STEERING_PROFILE_NAME_MAX_LENGTH + 1)}, "at most 100"),
        ({"revision": 0}, "positive integer"),
        ({"revision": True}, "positive integer"),
        ({"revision": "1"}, "positive integer"),
        ({"definition": object()}, "SteeringCurveDefinition"),
        ({"created_at": 1}, "canonical UTC"),
        ({"created_at": "2026-07-14T10:30:00Z"}, "canonical UTC"),
        ({"created_at": "2026-07-14T11:30:00.000000+01:00"}, "canonical UTC"),
        ({"updated_at": "yesterday"}, "canonical UTC"),
    ],
)
def test_invalid_stored_profile_metadata_is_rejected(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _profile(**changes)


def test_stored_profile_accepts_explicit_metadata_boundaries() -> None:
    profile = _profile(name="x" * STEERING_PROFILE_NAME_MAX_LENGTH)

    assert profile.revision == 1
    assert profile.definition is BUILT_IN_STEERING_CURVE


def test_timestamp_formatter_normalizes_aware_values_to_canonical_utc() -> None:
    local = datetime(2026, 7, 14, 12, 30, tzinfo=timezone(timedelta(hours=2)))

    assert canonical_utc_timestamp(local) == CREATED_AT
    assert canonical_utc_timestamp(datetime(2026, 7, 14, 10, 30, tzinfo=UTC)) == CREATED_AT
    with pytest.raises(ValueError, match="timezone-aware"):
        canonical_utc_timestamp(datetime(2026, 7, 14, 10, 30))


def test_integer_projection_and_definition_evaluation_preserve_resolution() -> None:
    float_pairs = steering_curve_as_float_pairs(BUILT_IN_STEERING_CURVE)

    assert tuple(round(speed * 10) for speed, _ in float_pairs) == (
        STEERING_CURVE_V1_SPEEDS_DECI_KPH
    )
    assert tuple(round(assistance * 1000) for _, assistance in float_pairs) == (
        1000,
        889,
        778,
        667,
        381,
        0,
        0,
        0,
    )
    for speed, _ in float_pairs:
        old_value = interpolate_speed_to_assistance(
            speed,
            ((0.0, 1.0), (30.0, 2.0 / 3.0), (100.0, 0.0)),
        )
        assert interpolate_steering_curve_definition(
            speed, BUILT_IN_STEERING_CURVE
        ) == pytest.approx(old_value, abs=ASSISTANCE_QUANTIZATION_TOLERANCE)


def test_definition_evaluation_holds_endpoint_values_outside_grid() -> None:
    assert interpolate_steering_curve_definition(-1.0, BUILT_IN_STEERING_CURVE) == 1.0
    assert interpolate_steering_curve_definition(251.0, BUILT_IN_STEERING_CURVE) == 0.0
