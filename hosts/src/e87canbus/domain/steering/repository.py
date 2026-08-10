"""Durable storage boundary for named, revisioned steering curves."""

from typing import Protocol

from e87canbus.domain.steering.curves import SteeringCurveDefinition, StoredSteeringProfile

STEERING_PROFILE_KIND = "steering profile"


class SteeringProfileRepository(Protocol):
    """Durable storage for named, revisioned steering curves."""

    """Durable storage for named, revisioned steering curves."""

    def list_profiles(self) -> tuple[StoredSteeringProfile, ...]: ...

    def get_profile(self, profile_id: str) -> StoredSteeringProfile | None: ...

    def create_profile(
        self, name: str, definition: SteeringCurveDefinition
    ) -> StoredSteeringProfile: ...

    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: SteeringCurveDefinition,
    ) -> StoredSteeringProfile: ...

    def delete_profile(self, profile_id: str, expected_revision: int) -> None: ...
