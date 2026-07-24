"""Persistence boundary for revisioned button-pad profiles."""

from typing import Protocol

from e87canbus.domain.button_profiles import ButtonProfileDefinition, StoredButtonProfile


class ButtonProfileRepositoryError(Exception):
    pass


class ButtonProfileStorageError(ButtonProfileRepositoryError):
    pass


class ButtonProfileNotFoundError(ButtonProfileRepositoryError):
    pass


class ButtonProfileNameConflictError(ButtonProfileRepositoryError):
    pass


class ButtonProfileProtectedError(ButtonProfileRepositoryError):
    pass


class ButtonProfileRevisionConflictError(ButtonProfileRepositoryError):
    def __init__(self, profile_id: str, expected_revision: int, actual_revision: int) -> None:
        self.profile_id, self.expected_revision, self.actual_revision = (
            profile_id,
            expected_revision,
            actual_revision,
        )
        super().__init__(
            f"button profile {profile_id} is at revision {actual_revision}, not {expected_revision}"
        )


class StoredButtonProfileDataError(ButtonProfileStorageError):
    def __init__(self, profile_id: str, reason: str) -> None:
        super().__init__(f"invalid stored button profile {profile_id}: {reason}")


class ButtonProfileRepository(Protocol):
    def list_profiles(self) -> tuple[StoredButtonProfile, ...]: ...
    def get_profile(self, profile_id: str) -> StoredButtonProfile | None: ...
    def get_selected_profile(self) -> StoredButtonProfile: ...
    def select_profile(self, profile_id: str, expected_revision: int) -> StoredButtonProfile: ...
    def create_profile(
        self, name: str, definition: ButtonProfileDefinition | None = None
    ) -> StoredButtonProfile: ...
    def update_profile(
        self,
        profile_id: str,
        expected_revision: int,
        name: str,
        definition: ButtonProfileDefinition,
    ) -> StoredButtonProfile: ...
    def delete_profile(self, profile_id: str, expected_revision: int) -> None: ...
