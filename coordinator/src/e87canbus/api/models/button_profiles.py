"""Strict HTTP models for durable button-pad profiles."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from e87canbus.api.models.steering import CANONICAL_UUID_PATTERN, StrictRequest
from e87canbus.domain.button_profiles import BUTTON_PROFILE_NAME_MAX_LENGTH
from e87canbus.domain.events import BUTTON_LED_COUNT


class SelectSteeringModeCommand(StrictRequest):
    type: Literal["select_steering_mode"]
    mode: Literal["auto", "manual"]


class ToggleAutomaticAssistanceCommand(StrictRequest):
    type: Literal["toggle_automatic_assistance"]


class AdjustManualAssistanceCommand(StrictRequest):
    type: Literal["adjust_manual_assistance"]
    delta: Literal[-1, 1]


class SetManualAssistanceLevelCommand(StrictRequest):
    type: Literal["set_manual_assistance_level"]
    level: int = Field(ge=0)


class SetMaximumAssistanceCommand(StrictRequest):
    type: Literal["set_maximum_assistance"]
    enabled: bool


class ToggleMaximumAssistanceCommand(StrictRequest):
    type: Literal["toggle_maximum_assistance"]


class StartHighBeamStrobeCommand(StrictRequest):
    type: Literal["start_high_beam_strobe"]


ButtonProfileCommand = Annotated[
    SelectSteeringModeCommand
    | ToggleAutomaticAssistanceCommand
    | AdjustManualAssistanceCommand
    | SetManualAssistanceLevelCommand
    | SetMaximumAssistanceCommand
    | ToggleMaximumAssistanceCommand
    | StartHighBeamStrobeCommand,
    Field(discriminator="type"),
]


class ButtonProfileDefinitionRequest(StrictRequest):
    schema_version: Literal[1]
    slots: list[ButtonProfileCommand | None] = Field(
        min_length=BUTTON_LED_COUNT, max_length=BUTTON_LED_COUNT
    )


class CreateButtonProfileRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=BUTTON_PROFILE_NAME_MAX_LENGTH)
    definition: ButtonProfileDefinitionRequest | None = None


class UpdateButtonProfileRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=BUTTON_PROFILE_NAME_MAX_LENGTH)
    expected_revision: int = Field(ge=1)
    definition: ButtonProfileDefinitionRequest


class ButtonProfileDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    slots: tuple[ButtonProfileCommand | None, ...] = Field(
        min_length=BUTTON_LED_COUNT, max_length=BUTTON_LED_COUNT
    )


class ButtonProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(pattern=CANONICAL_UUID_PATTERN)
    name: str = Field(min_length=1, max_length=BUTTON_PROFILE_NAME_MAX_LENGTH)
    revision: int = Field(ge=1)
    definition: ButtonProfileDefinitionResponse
    created_at: str
    updated_at: str
