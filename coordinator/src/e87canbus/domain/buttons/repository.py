"""Durable storage boundary for button-pad profiles and the selected one."""

from typing import Protocol

from e87canbus.domain.buttons.profiles import ButtonProfileDefinition, StoredButtonProfile

BUTTON_PROFILE_KIND = "button profile"


class ButtonProfileRepository(Protocol):
    """Durable button-profile storage, including which profile is selected."""

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
