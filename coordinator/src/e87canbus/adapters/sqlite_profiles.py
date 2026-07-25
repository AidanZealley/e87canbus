"""SQLite persistence for complete, revisioned steering profiles."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from e87canbus.adapters.sqlite_database import (
    BUILT_IN_PROFILE_ID as BUILT_IN_PROFILE_ID,
)
from e87canbus.adapters.sqlite_database import (
    BUILT_IN_PROFILE_NAME as BUILT_IN_PROFILE_NAME,
)
from e87canbus.adapters.sqlite_database import (
    CURRENT_MIGRATION_VERSION as CURRENT_MIGRATION_VERSION,
)
from e87canbus.adapters.sqlite_database import (
    SqliteApplicationDatabase,
)
from e87canbus.adapters.sqlite_revisioned_profiles import (
    RevisionedProfileSpec,
    SqliteRevisionedProfileRepository,
    utc_now,
)
from e87canbus.domain.profile_repository import STEERING_PROFILE_KIND
from e87canbus.domain.steering import (
    SteeringCurveDefinition,
    StoredSteeringProfile,
    canonical_steering_curve_bytes,
    decode_steering_curve,
    steering_curve_fingerprint,
    validate_steering_profile_name,
)

STEERING_PROFILE_SPEC = RevisionedProfileSpec[SteeringCurveDefinition, StoredSteeringProfile](
    kind=STEERING_PROFILE_KIND,
    table="steering_profiles",
    encode=canonical_steering_curve_bytes,
    decode=decode_steering_curve,
    fingerprint=steering_curve_fingerprint,
    validate_name=validate_steering_profile_name,
    build=StoredSteeringProfile,
)


class SqliteSteeringProfileRepository(
    SqliteRevisionedProfileRepository[SteeringCurveDefinition, StoredSteeringProfile]
):
    """The shared revisioned-profile mechanism bound to the steering curve codec."""

    def __init__(
        self,
        database_path: str | Path | SqliteApplicationDatabase,
        *,
        clock: Callable[[], datetime] = utc_now,
        identifier_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        super().__init__(
            STEERING_PROFILE_SPEC,
            database_path,
            clock=clock,
            identifier_factory=identifier_factory,
        )
