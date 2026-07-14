"""Domain-facing persistence boundary for named steering profiles."""

from typing import Protocol

from e87canbus.features.steering import SteeringCurveDefinition, StoredSteeringProfile


class SteeringProfileRepositoryError(Exception):
    """Base class for failures exposed by a steering-profile repository."""


class ProfileNotFoundError(SteeringProfileRepositoryError):
    def __init__(self, profile_id: str) -> None:
        self.profile_id = profile_id
        super().__init__(f"steering profile not found: {profile_id}")


class ProfileRevisionConflictError(SteeringProfileRepositoryError):
    def __init__(self, profile_id: str, expected_revision: int, actual_revision: int) -> None:
        self.profile_id = profile_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            f"steering profile {profile_id} is at revision {actual_revision}, "
            f"not {expected_revision}"
        )


class ProfileNameConflictError(SteeringProfileRepositoryError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"steering profile name already exists: {name}")


class SteeringProfileStorageError(SteeringProfileRepositoryError):
    """The repository could not safely read or commit its durable state."""


class StoredProfileDataError(SteeringProfileStorageError):
    def __init__(self, profile_id: str, reason: str) -> None:
        self.profile_id = profile_id
        self.reason = reason
        super().__init__(f"invalid stored steering profile {profile_id}: {reason}")


class SteeringProfileRepository(Protocol):
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
