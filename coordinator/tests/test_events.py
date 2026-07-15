import pytest
from e87canbus.application.events import (
    ButtonLedState,
    LedColour,
    SetSteeringAssistance,
    SteeringCommandReason,
)


def test_steering_effect_rejects_out_of_range_assistance() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        SetSteeringAssistance(1.1, SteeringCommandReason.MAXIMUM)


def test_button_led_state_rejects_partial_and_unknown_colours() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        ButtonLedState((LedColour.OFF,) * 15)
    with pytest.raises(ValueError, match="known LED colours"):
        ButtonLedState((LedColour.OFF,) * 15 + ("off",))  # type: ignore[arg-type]
