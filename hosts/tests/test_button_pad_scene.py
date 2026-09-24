"""The complete independent pad scene and its validated document."""

import pytest
from e87canbus.api.models.button_pad import ButtonPadScene
from e87canbus.domain.buttons.profiles import (
    ActiveButtonProfile,
    BlinkAnimation,
    BreatheAnimation,
    ButtonSlot,
    button_profile_definition_with,
)
from e87canbus.domain.buttons.scene import resting_rgb
from e87canbus.domain.intents import SelectSteeringMode, ToggleAutomaticAssistance
from e87canbus.domain.state import ApplicationState, NormalSteering, SteeringMode
from pydantic import ValidationError


def test_scene_resolves_all_positions_and_active_only_animations() -> None:
    profile = ActiveButtonProfile(
        "custom",
        button_profile_definition_with(
            {
                0: ButtonSlot(
                    SelectSteeringMode(SteeringMode.AUTO),
                    (255, 191, 0),
                    animation=BlinkAnimation(100, 200),
                ),
                4: ButtonSlot(
                    SelectSteeringMode(SteeringMode.MANUAL),
                    (0, 0, 255),
                    animation=BreatheAnimation(2000, 8, 255),
                ),
                15: ButtonSlot(ToggleAutomaticAssistance(), (12, 34, 56)),
            }
        ),
    )

    automatic = ButtonPadScene.from_profile(ApplicationState(), profile)
    assert automatic.schema_version == 1
    assert automatic.brightness == 255
    assert len(automatic.buttons) == 16
    assert automatic.buttons[0].colour == [255, 191, 0]
    assert automatic.buttons[0].animation is not None
    assert automatic.buttons[0].animation.model_dump() == {
        "type": "blink", "on_ms": 100, "off_ms": 200
    }
    assert automatic.buttons[4].colour == [0, 0, 8]
    assert automatic.buttons[4].animation is None
    assert automatic.buttons[1].model_dump() == {
        "assigned": False, "colour": [0, 0, 0], "animation": None
    }

    manual = ButtonPadScene.from_profile(
        ApplicationState(steering=NormalSteering(SteeringMode.MANUAL)), profile
    )
    assert manual.buttons[0].colour == [8, 6, 0]
    assert manual.buttons[0].animation is None
    assert manual.buttons[4].colour == [0, 0, 255]
    assert manual.buttons[4].animation is not None
    assert manual.buttons[4].animation.type == "breathe"
    assert manual.buttons[15].colour == list(resting_rgb((12, 34, 56)))
    assert ButtonPadScene.model_validate_json(manual.model_dump_json()) == manual


def test_scene_rejects_incomplete_oversized_and_malformed_documents() -> None:
    scene = ButtonPadScene.from_profile(
        ApplicationState(), ActiveButtonProfile("empty", button_profile_definition_with({}))
    ).model_dump()

    for buttons in (scene["buttons"][:-1], scene["buttons"] + [scene["buttons"][0]]):
        with pytest.raises(ValidationError):
            ButtonPadScene.model_validate({**scene, "buttons": buttons})

    with pytest.raises(ValidationError):
        ButtonPadScene.model_validate({**scene, "can_id": 0x700})
    with pytest.raises(ValidationError):
        ButtonPadScene.model_validate({**scene, "buttons": [{"assigned": False}] * 16})
    with pytest.raises(ValidationError):
        ButtonPadScene.model_validate({**scene, "brightness": True})
    scene["buttons"][0]["animation"] = {
        "type": "breathe", "period_ms": 2000, "minimum": 9, "maximum": 8
    }
    with pytest.raises(ValidationError):
        ButtonPadScene.model_validate(scene)
