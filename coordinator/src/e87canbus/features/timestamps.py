"""Canonical UTC timestamp helpers shared by persisted domain values."""

from datetime import UTC, datetime


def canonical_utc_timestamp(value: datetime) -> str:
    """Return UTC text with six fractional digits and a trailing ``Z``."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def validate_canonical_utc_timestamp(value: str, field_name: str) -> None:
    """Reject timestamps outside the project's canonical persisted representation."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be canonical UTC text") from error
    if canonical_utc_timestamp(parsed) != value:
        raise ValueError(f"{field_name} must be canonical UTC text")
