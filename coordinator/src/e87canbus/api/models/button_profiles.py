"""Strict HTTP models for durable button-pad profiles."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model

from e87canbus.api.models.steering import CANONICAL_UUID_PATTERN, StrictRequest
from e87canbus.domain.button_commands import BUTTON_COMMAND_CATALOGUE, ButtonCommandSpec
from e87canbus.domain.button_profiles import BUTTON_PROFILE_NAME_MAX_LENGTH
from e87canbus.domain.events import BUTTON_LED_COUNT


def _command_model(spec: ButtonCommandSpec) -> type[StrictRequest]:
    """Build one request model from a catalogue entry.

    The models are generated rather than hand-written so the tag, the field names and
    their shapes are stated once, in the catalogue. Names follow the previous
    hand-written classes ("SelectSteeringModeCommand"), because they are the schema
    names in the published OpenAPI document and in the generated frontend types.
    """

    fields: dict[str, Any] = {"type": (Literal[spec.tag], ...)}
    for field in spec.fields:
        annotation = field.annotation
        constraint = Field() if field.minimum is None else Field(ge=field.minimum)
        fields[field.name] = (annotation, constraint)
    name = "".join(part.title() for part in spec.tag.split("_")) + "Command"
    return create_model(name, __base__=StrictRequest, __module__=__name__, **fields)


_COMMAND_MODELS = tuple(_command_model(spec) for spec in BUTTON_COMMAND_CATALOGUE)

# A discriminated union over every generated model, so an added catalogue entry becomes
# an accepted request body without a second list to keep in step.
ButtonProfileCommand = Annotated[
    Union[_COMMAND_MODELS],  # type: ignore[valid-type]  # noqa: UP007
    Field(discriminator="type"),
]

globals().update({model.__name__: model for model in _COMMAND_MODELS})


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
