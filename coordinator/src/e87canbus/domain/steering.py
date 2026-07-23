"""Steering-curve domain values and pure assistance calculations."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from e87canbus.domain.timestamps import (
    canonical_utc_timestamp as canonical_utc_timestamp,
)
from e87canbus.domain.timestamps import (
    validate_canonical_utc_timestamp,
)

STEERING_CURVE_SCHEMA_VERSION = 1
STEERING_CURVE_V1_SPEEDS_DECI_KPH = (0, 100, 200, 300, 600, 1000, 1600, 2500)
STEERING_PROFILE_NAME_MAX_LENGTH = 100

# One per-mille is the authoritative assistance resolution. Rounding a value to
# that resolution introduces at most half a per-mille of calculation error.
ASSISTANCE_QUANTIZATION_TOLERANCE = 0.0005
STEERING_CURVE_CONFORMANCE_TOLERANCE = 1e-12


@dataclass(frozen=True)
class SteeringCurvePoint:
    speed_deci_kph: int
    assistance_per_mille: int


@dataclass(frozen=True)
class SteeringCurveDefinition:
    schema_version: int
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


class SteeringCurveActivationStatus(StrEnum):
    ACTIVE = "active"
    ACTIVATING = "activating"
    ACTIVATION_FAILED = "activation_failed"


@dataclass(frozen=True)
class ActiveSteeringCurve:
    """The immutable curve projection owned by one coordinator runtime."""

    definition: SteeringCurveDefinition
    fingerprint: str
    activation_revision: int
    saved_profile_id: str | None = None
    saved_profile_revision: int | None = None

    def __post_init__(self) -> None:
        validate_active_steering_curve(self)


def validate_steering_curve_definition(definition: SteeringCurveDefinition) -> None:
    """Raise ``ValueError`` when a curve is outside the versioned domain contract."""

    if not isinstance(definition, SteeringCurveDefinition):
        raise ValueError("definition must be a SteeringCurveDefinition")
    if type(definition.schema_version) is not int:  # bool is not a domain integer
        raise ValueError("schema_version must be an integer")
    if definition.schema_version != STEERING_CURVE_SCHEMA_VERSION:
        raise ValueError(f"unsupported steering curve schema_version: {definition.schema_version}")
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


def validate_stored_steering_profile(profile: StoredSteeringProfile) -> None:
    """Raise ``ValueError`` when stored identity or revision metadata is invalid."""

    validate_steering_profile_id(profile.profile_id)
    validate_steering_profile_name(profile.name)
    if type(profile.revision) is not int or profile.revision < 1:
        raise ValueError("profile revision must be a positive integer")
    if not isinstance(profile.definition, SteeringCurveDefinition):
        raise ValueError("profile definition must be a SteeringCurveDefinition")
    validate_steering_curve_definition(profile.definition)
    validate_canonical_utc_timestamp(profile.created_at, "created_at")
    validate_canonical_utc_timestamp(profile.updated_at, "updated_at")


def validate_active_steering_curve(active: ActiveSteeringCurve) -> None:
    """Raise ``ValueError`` when an active runtime projection is inconsistent."""

    if not isinstance(active, ActiveSteeringCurve):
        raise ValueError("active curve must be an ActiveSteeringCurve")
    if not isinstance(active.definition, SteeringCurveDefinition):
        raise ValueError("active definition must be a SteeringCurveDefinition")
    validate_steering_curve_definition(active.definition)
    if active.fingerprint != steering_curve_fingerprint(active.definition):
        raise ValueError("active fingerprint must match the definition")
    if type(active.activation_revision) is not int or active.activation_revision < 1:
        raise ValueError("activation_revision must be a positive integer")
    if (active.saved_profile_id is None) != (active.saved_profile_revision is None):
        raise ValueError("saved profile ID and revision must be supplied together")
    if active.saved_profile_id is not None:
        validate_steering_profile_id(active.saved_profile_id, field_name="saved_profile_id")
    if active.saved_profile_revision is not None and (
        type(active.saved_profile_revision) is not int or active.saved_profile_revision < 1
    ):
        raise ValueError("saved_profile_revision must be a positive integer")


def validate_steering_profile_name(name: str) -> None:
    """Raise ``ValueError`` when a profile name is outside the stored-profile contract."""

    if not isinstance(name, str):
        raise ValueError("profile name must be text")
    if not name or name != name.strip():
        raise ValueError("profile name must be non-empty and trimmed")
    if len(name) > STEERING_PROFILE_NAME_MAX_LENGTH:
        raise ValueError(
            f"profile name must contain at most {STEERING_PROFILE_NAME_MAX_LENGTH} characters"
        )


def validate_steering_profile_id(profile_id: str, *, field_name: str = "profile_id") -> None:
    """Raise ``ValueError`` unless an ID is canonical lowercase UUID text."""

    if not isinstance(profile_id, str):
        raise ValueError(f"{field_name} must be UUID text")
    try:
        canonical_profile_id = str(UUID(profile_id))
    except (ValueError, AttributeError) as error:
        raise ValueError(f"{field_name} must be UUID text") from error
    if profile_id != canonical_profile_id:
        raise ValueError(f"{field_name} must use canonical UUID text")


def canonical_steering_curve_bytes(definition: SteeringCurveDefinition) -> bytes:
    """Serialize integer-only definition data as sorted, compact UTF-8 JSON."""

    validate_steering_curve_definition(definition)
    value = {
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


def initial_active_steering_curve(
    definition: SteeringCurveDefinition = BUILT_IN_STEERING_CURVE,
    *,
    saved_profile_id: str | None = None,
    saved_profile_revision: int | None = None,
) -> ActiveSteeringCurve:
    """Build revision one after startup composition has selected a definition."""

    validate_steering_curve_definition(definition)
    return ActiveSteeringCurve(
        definition=definition,
        fingerprint=steering_curve_fingerprint(definition),
        activation_revision=1,
        saved_profile_id=saved_profile_id,
        saved_profile_revision=saved_profile_revision,
    )


def interpolate_steering_curve_definition(
    speed_kph: float,
    definition: SteeringCurveDefinition,
) -> float:
    """Evaluate the definition's versioned algorithm in binary64 calculation units."""

    validate_steering_curve_definition(definition)
    if not math.isfinite(speed_kph):
        raise ValueError("speed_kph must be finite")
    return interpolate_monotone_cubic_v1(speed_kph * 10.0, definition.points)


def clamp_manual_level(level: int, level_count: int) -> int:
    if level_count < 1:
        raise ValueError("level_count must be at least 1")
    return min(max(level, 0), level_count - 1)


def interpolate_monotone_cubic_v1(
    speed_deci_kph: float,
    points: Sequence[SteeringCurvePoint],
) -> float:
    """Evaluate Steffen/D3 monotone Hermite points expressed in integer input units."""

    if len(points) < 2:
        raise ValueError("monotone-cubic-v1 requires at least two points")
    if not math.isfinite(speed_deci_kph):
        raise ValueError("speed_deci_kph must be finite")

    x = tuple(float(point.speed_deci_kph) for point in points)
    y = tuple(point.assistance_per_mille / 1000.0 for point in points)
    spans = tuple(right - left for left, right in zip(x, x[1:], strict=False))
    if any(not math.isfinite(span) or span <= 0.0 for span in spans):
        raise ValueError("monotone-cubic-v1 speeds must be finite and strictly increasing")

    evaluation_x = speed_deci_kph
    if evaluation_x <= x[0]:
        return y[0]
    if evaluation_x >= x[-1]:
        return y[-1]

    for index, point_x in enumerate(x):
        if evaluation_x == point_x:
            return y[index]

    tangents = _steffen_tangents(x, y)
    for index, (left_x, right_x) in enumerate(zip(x, x[1:], strict=False)):
        if evaluation_x >= right_x:
            continue
        span = right_x - left_x
        progress = (evaluation_x - left_x) / span
        progress_squared = progress * progress
        progress_cubed = progress_squared * progress
        value = (
            (2.0 * progress_cubed - 3.0 * progress_squared + 1.0) * y[index]
            + (progress_cubed - 2.0 * progress_squared + progress) * span * tangents[index]
            + (-2.0 * progress_cubed + 3.0 * progress_squared) * y[index + 1]
            + (progress_cubed - progress_squared) * span * tangents[index + 1]
        )
        return min(1.0, max(0.0, value))

    return y[-1]


def _steffen_tangents(x: tuple[float, ...], y: tuple[float, ...]) -> tuple[float, ...]:
    if len(x) == 2:
        secant = (y[1] - y[0]) / (x[1] - x[0])
        return (secant, secant)
    interior = tuple(
        _steffen_interior_tangent(
            x[index - 1],
            y[index - 1],
            x[index],
            y[index],
            x[index + 1],
            y[index + 1],
        )
        for index in range(1, len(x) - 1)
    )
    first_secant = (y[1] - y[0]) / (x[1] - x[0])
    last_secant = (y[-1] - y[-2]) / (x[-1] - x[-2])
    return (
        (3.0 * first_secant - interior[0]) / 2.0,
        *interior,
        (3.0 * last_secant - interior[-1]) / 2.0,
    )


def _steffen_interior_tangent(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    left_span = x1 - x0
    right_span = x2 - x1
    left_secant = (y1 - y0) / left_span
    right_secant = (y2 - y1) / right_span
    weighted_secant = (left_secant * right_span + right_secant * left_span) / (
        left_span + right_span
    )
    sign_sum = _d3_sign(left_secant) + _d3_sign(right_secant)
    return sign_sum * min(
        abs(left_secant),
        abs(right_secant),
        0.5 * abs(weighted_secant),
    )


def _d3_sign(value: float) -> int:
    return -1 if value < 0.0 else 1
