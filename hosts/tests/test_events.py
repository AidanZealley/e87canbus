import pytest
from e87canbus.domain.events import (
    ButtonLedState,
    SetSteeringAssistance,
    SteeringCommandReason,
)
from e87canbus.domain.state import ButtonVisual


def test_steering_effect_rejects_out_of_range_assistance() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        SetSteeringAssistance(1.1, SteeringCommandReason.MAXIMUM)


def test_button_led_state_requires_one_visual_state_per_button() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        ButtonLedState((ButtonVisual.UNASSIGNED,) * 15)
