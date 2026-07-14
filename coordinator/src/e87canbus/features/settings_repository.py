"""Domain-facing persistence boundary for application settings."""

from typing import Protocol

from e87canbus.features.application_settings import (
    ApplicationSettings,
    ApplicationSettingsUpdate,
)


class ApplicationSettingsRepositoryError(Exception):
    """Base class for settings repository failures."""


class SettingsRevisionConflictError(ApplicationSettingsRepositoryError):
    def __init__(self, expected_revision: int, current_revision: int) -> None:
        self.expected_revision = expected_revision
        self.current_revision = current_revision
        super().__init__(
            f"application settings are at revision {current_revision}, not {expected_revision}"
        )


class SettingsStorageError(ApplicationSettingsRepositoryError):
    """Settings could not be read or committed safely."""


class StoredSettingsDataError(SettingsStorageError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"invalid stored application settings: {reason}")


class ApplicationSettingsRepository(Protocol):
    def get_settings(self) -> ApplicationSettings: ...

    def update_settings(
        self,
        expected_revision: int,
        candidate: ApplicationSettingsUpdate,
    ) -> ApplicationSettings: ...
