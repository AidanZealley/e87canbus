"""The complete validated button-pad configuration shared by storage and HTTP."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from e87canbus.api.models.steering import StrictRequest
from e87canbus.domain.buttons.profiles import (
    BLINK_DURATION_MAX_MS,
    BLINK_DURATION_MIN_MS,
    BREATHE_PERIOD_MAX_MS,
    BREATHE_PERIOD_MIN_MS,
    RGB_CHANNEL_MAX,
    ActiveButtonProfile,
    BlinkAnimation,
    BreatheAnimation,
)
from e87canbus.domain.buttons.scene import ResolvedButton, resolve_button_pad
from e87canbus.domain.events import BUTTON_LED_COUNT
from e87canbus.domain.state import ApplicationState

RgbChannel = Annotated[int, Field(ge=0, le=RGB_CHANNEL_MAX)]


class ButtonPadDeviceStatus(StrictRequest):
    """The first button-pad status document has no role-specific fields."""


class ButtonPadStatus(StrictRequest):
    status_version: Literal[1]
    applied_configuration_generation: int = Field(ge=0, le=9_007_199_254_740_991)
    configuration_error: str | None
    device: ButtonPadDeviceStatus


class ButtonPadPressRequest(StrictRequest):
    button_index: int = Field(ge=0, lt=BUTTON_LED_COUNT)


class BreatheSceneAnimation(StrictRequest):
    type: Literal["breathe"]
    period_ms: int = Field(ge=BREATHE_PERIOD_MIN_MS, le=BREATHE_PERIOD_MAX_MS)
    minimum: RgbChannel
    maximum: RgbChannel

    @model_validator(mode="after")
    def _ordered_brightness(self) -> Self:
        if self.minimum > self.maximum:
            raise ValueError("breathe minimum brightness must not exceed its maximum")
        return self


class BlinkSceneAnimation(StrictRequest):
    type: Literal["blink"]
    on_ms: int = Field(ge=BLINK_DURATION_MIN_MS, le=BLINK_DURATION_MAX_MS)
    off_ms: int = Field(ge=BLINK_DURATION_MIN_MS, le=BLINK_DURATION_MAX_MS)


SceneAnimation = Annotated[BreatheSceneAnimation | BlinkSceneAnimation, Field(discriminator="type")]


class SceneButton(StrictRequest):
    assigned: bool
    colour: list[RgbChannel] = Field(min_length=3, max_length=3)
    animation: SceneAnimation | None


class ButtonPadScene(StrictRequest):
    schema_version: Literal[1]
    brightness: RgbChannel
    buttons: list[SceneButton] = Field(
        min_length=BUTTON_LED_COUNT, max_length=BUTTON_LED_COUNT
    )

    @classmethod
    def from_profile(cls, state: ApplicationState, profile: ActiveButtonProfile) -> Self:
        return cls.from_resolved_buttons(resolve_button_pad(state, profile))

    @classmethod
    def from_resolved_buttons(cls, resolved: tuple[ResolvedButton, ...]) -> Self:
        buttons = []
        for button in resolved:
            animation = button.animation
            scene_animation: SceneAnimation | None
            if isinstance(animation, BreatheAnimation):
                scene_animation = BreatheSceneAnimation(
                    type="breathe",
                    period_ms=animation.period_ms,
                    minimum=animation.minimum,
                    maximum=animation.maximum,
                )
            elif isinstance(animation, BlinkAnimation):
                scene_animation = BlinkSceneAnimation(
                    type="blink", on_ms=animation.on_ms, off_ms=animation.off_ms
                )
            else:
                scene_animation = None
            buttons.append(
                SceneButton(
                    assigned=button.assigned, colour=list(button.colour), animation=scene_animation
                )
            )
        return cls(schema_version=1, brightness=255, buttons=buttons)


class ButtonPadConfigurationEnvelope(StrictRequest):
    generation: int = Field(ge=0, le=9_007_199_254_740_991)
    configuration: ButtonPadScene
