"""Steering-curve domain values and pure assistance calculations."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

SpeedAssistanceCurve = Sequence[tuple[float, float]]

STEERING_CURVE_SCHEMA_VERSION = 1
STEERING_CURVE_V1_SPEEDS_DECI_KPH = (0, 100, 200, 300, 600, 1000, 1600, 2500)
STEERING_PROFILE_NAME_MAX_LENGTH = 100

# One per-mille is the authoritative assistance resolution. Rounding a value to
# that resolution introduces at most half a per-mille of calculation error.
ASSISTANCE_QUANTIZATION_TOLERANCE = 0.0005


class CurveInterpolation(StrEnum):
    LINEAR_V1 = "linear-v1"
    MONOTONE_CUBIC_V1 = "monotone-cubic-v1"


@dataclass(frozen=True)
class SteeringCurvePoint:
    speed_deci_kph: int
    assistance_per_mille: int


@dataclass(frozen=True)
class SteeringCurveDefinition:
    schema_version: int
    interpolation: CurveInterpolation
    points: tuple[SteeringCurvePoint, ...]

    def __post_init__(self) -> None:
        validate_steering_curve_definition(self)


@dataclass(frozen=True)
class StoredSteeringProfile:
    profile_id: str
    name: str
    revision: int
    definition: SteeringCurveDefinition
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        validate_stored_steering_profile(self)


def validate_steering_curve_definition(definition: SteeringCurveDefinition) -> None:
    """Raise ``ValueError`` when a curve is outside the versioned domain contract."""

    if type(definition.schema_version) is not int:  # bool is not a domain integer
        raise ValueError("schema_version must be an integer")
    if definition.schema_version != STEERING_CURVE_SCHEMA_VERSION:
        raise ValueError(f"unsupported steering curve schema_version: {definition.schema_version}")
    if not isinstance(definition.interpolation, CurveInterpolation):
        raise ValueError("interpolation must be a CurveInterpolation value")
    if definition.interpolation is not CurveInterpolation.LINEAR_V1:
        raise ValueError(f"unsupported steering curve interpolation: {definition.interpolation}")
    if not isinstance(definition.points, tuple):
        raise ValueError("points must be an immutable tuple")
    if len(definition.points) != len(STEERING_CURVE_V1_SPEEDS_DECI_KPH):
        raise ValueError(
            f"schema version 1 requires {len(STEERING_CURVE_V1_SPEEDS_DECI_KPH)} points"
        )
    if any(not isinstance(point, SteeringCurvePoint) for point in definition.points):
        raise ValueError("points must contain SteeringCurvePoint values")

    speeds = tuple(point.speed_deci_kph for point in definition.points)
    assistance = tuple(point.assistance_per_mille for point in definition.points)
    if any(type(speed) is not int for speed in speeds):
        raise ValueError("speed_deci_kph must be an integer")
    if any(speed < 0 for speed in speeds):
        raise ValueError("speed_deci_kph must be non-negative")
    if any(left >= right for left, right in zip(speeds, speeds[1:], strict=False)):
        raise ValueError("speed_deci_kph values must be strictly increasing")
    if speeds != STEERING_CURVE_V1_SPEEDS_DECI_KPH:
        raise ValueError("speeds must exactly match the schema-version-1 grid")
    if any(type(value) is not int for value in assistance):
        raise ValueError("assistance_per_mille must be an integer")
    if any(not 0 <= value <= 1000 for value in assistance):
        raise ValueError("assistance_per_mille must be between 0 and 1000")
    if any(left < right for left, right in zip(assistance, assistance[1:], strict=False)):
        raise ValueError("assistance must be non-increasing as speed rises")


def canonical_utc_timestamp(value: datetime) -> str:
    """Return the profile timestamp format: UTC with six fractional digits and ``Z``."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("profile timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_stored_steering_profile(profile: StoredSteeringProfile) -> None:
    """Raise ``ValueError`` when stored identity or revision metadata is invalid."""

    if not isinstance(profile.profile_id, str):
        raise ValueError("profile_id must be UUID text")
    try:
        canonical_profile_id = str(UUID(profile.profile_id))
    except (ValueError, AttributeError) as error:
        raise ValueError("profile_id must be UUID text") from error
    if profile.profile_id != canonical_profile_id:
        raise ValueError("profile_id must use canonical UUID text")
    if not isinstance(profile.name, str):
        raise ValueError("profile name must be text")
    if not profile.name or profile.name != profile.name.strip():
        raise ValueError("profile name must be non-empty and trimmed")
    if len(profile.name) > STEERING_PROFILE_NAME_MAX_LENGTH:
        raise ValueError(
            f"profile name must contain at most {STEERING_PROFILE_NAME_MAX_LENGTH} characters"
        )
    if type(profile.revision) is not int or profile.revision < 1:
        raise ValueError("profile revision must be a positive integer")
    if not isinstance(profile.definition, SteeringCurveDefinition):
        raise ValueError("profile definition must be a SteeringCurveDefinition")
    validate_steering_curve_definition(profile.definition)
    _validate_canonical_timestamp(profile.created_at, "created_at")
    _validate_canonical_timestamp(profile.updated_at, "updated_at")


def _validate_canonical_timestamp(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be canonical UTC text") from error
    if canonical_utc_timestamp(parsed) != value:
        raise ValueError(f"{field_name} must be canonical UTC text")


def canonical_steering_curve_bytes(definition: SteeringCurveDefinition) -> bytes:
    """Serialize integer-only definition data as sorted, compact UTF-8 JSON."""

    validate_steering_curve_definition(definition)
    value = {
        "interpolation": definition.interpolation.value,
        "points": [
            {
                "assistance_per_mille": point.assistance_per_mille,
                "speed_deci_kph": point.speed_deci_kph,
            }
            for point in definition.points
        ],
        "schema_version": definition.schema_version,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def steering_curve_fingerprint(definition: SteeringCurveDefinition) -> str:
    """Return the lowercase SHA-256 identity of a definition's canonical bytes."""

    return sha256(canonical_steering_curve_bytes(definition)).hexdigest()


BUILT_IN_STEERING_CURVE = SteeringCurveDefinition(
    schema_version=STEERING_CURVE_SCHEMA_VERSION,
    interpolation=CurveInterpolation.LINEAR_V1,
    points=tuple(
        SteeringCurvePoint(speed_deci_kph=speed, assistance_per_mille=assistance)
        for speed, assistance in zip(
            STEERING_CURVE_V1_SPEEDS_DECI_KPH,
            (1000, 889, 778, 667, 381, 0, 0, 0),
            strict=True,
        )
    ),
)


def default_steering_curve_definition() -> SteeringCurveDefinition:
    """Return the one immutable built-in steering curve."""

    return BUILT_IN_STEERING_CURVE


def steering_curve_as_float_pairs(
    definition: SteeringCurveDefinition,
) -> tuple[tuple[float, float], ...]:
    """Project authoritative integer units to calculation units of km/h and ``0.0..1.0``."""

    validate_steering_curve_definition(definition)
    return tuple(
        (point.speed_deci_kph / 10.0, point.assistance_per_mille / 1000.0)
        for point in definition.points
    )


def interpolate_steering_curve_definition(
    speed_kph: float,
    definition: SteeringCurveDefinition,
) -> float:
    """Evaluate a validated definition, holding the nearest endpoint outside its grid."""

    return interpolate_speed_to_assistance(speed_kph, steering_curve_as_float_pairs(definition))


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
