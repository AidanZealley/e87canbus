"""Strict HTTP models for durable button-pad profiles."""

from typing import Annotated, Any, Literal, Self, Union

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from e87canbus.api.models.steering import CANONICAL_UUID_PATTERN, StrictRequest
from e87canbus.domain.buttons.catalogue import BUTTON_COMMAND_CATALOGUE, ButtonCommandSpec
from e87canbus.domain.buttons.profiles import (
    BLINK_DURATION_MAX_MS,
    BLINK_DURATION_MIN_MS,
    BREATHE_PERIOD_MAX_MS,
    BREATHE_PERIOD_MIN_MS,
    BUTTON_PROFILE_NAME_MAX_LENGTH,
    RGB_CHANNEL_MAX,
)
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

RgbChannel = Annotated[int, Field(ge=0, le=RGB_CHANNEL_MAX)]


class BreatheAnimationRequest(StrictRequest):
    """Bounds mirror the button-pad track payload, so an accepted animation is runnable."""

    kind: Literal["breathe"]
    period_ms: int = Field(ge=BREATHE_PERIOD_MIN_MS, le=BREATHE_PERIOD_MAX_MS)
    minimum: RgbChannel
    maximum: RgbChannel

    @model_validator(mode="after")
    def _ordered_brightness(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("breathe minimum brightness must not exceed its maximum")
        return self


class BlinkAnimationRequest(StrictRequest):
    kind: Literal["blink"]
    on_ms: int = Field(ge=BLINK_DURATION_MIN_MS, le=BLINK_DURATION_MAX_MS)
    off_ms: int = Field(ge=BLINK_DURATION_MIN_MS, le=BLINK_DURATION_MAX_MS)


ButtonProfileAnimation = Annotated[
    Union[BreatheAnimationRequest, BlinkAnimationRequest],  # noqa: UP007
    Field(discriminator="kind"),
]


class ButtonProfileSlotRequest(StrictRequest):
    """One authored button: presentation is a sibling of the command, not part of it.

    ``active_colour`` is reserved and typed as null so a client cannot start depending on
    a second colour before the renderer honours one. Whether an animation is permitted at
    all depends on the bound command having an observable condition, which the domain
    decides at the save boundary.
    """

    command: ButtonProfileCommand
    colour: list[RgbChannel] = Field(min_length=3, max_length=3)
    active_colour: None = None
    animation: ButtonProfileAnimation | None = None


class ButtonProfileDefinitionRequest(StrictRequest):
    slots: list[ButtonProfileSlotRequest | None] = Field(
        min_length=BUTTON_LED_COUNT, max_length=BUTTON_LED_COUNT
    )


class CreateButtonProfileRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=BUTTON_PROFILE_NAME_MAX_LENGTH)
    definition: ButtonProfileDefinitionRequest | None = None


class UpdateButtonProfileRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=BUTTON_PROFILE_NAME_MAX_LENGTH)
    expected_revision: int = Field(ge=1)
    definition: ButtonProfileDefinitionRequest


class ButtonProfileSlotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: ButtonProfileCommand
    colour: tuple[RgbChannel, RgbChannel, RgbChannel]
    active_colour: None
    animation: ButtonProfileAnimation | None


class ButtonProfileDefinitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: tuple[ButtonProfileSlotResponse | None, ...] = Field(
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
