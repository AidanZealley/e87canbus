"""Persistence boundary for revisioned button-pad profiles."""

from typing import Protocol

from e87canbus.domain.button_profiles import ButtonProfileDefinition, StoredButtonProfile

BUTTON_PROFILE_KIND = "button profile"


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
