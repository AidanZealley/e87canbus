import pytest
from e87canbus.application.events import (
    ButtonLedState,
    ButtonPressed,
    ControlTimerElapsed,
    LedColour,
    SetSteeringAssistance,
    SpeedObserved,
    SteeringCommandReason,
)
from e87canbus.application.state import SpeedSample
from e87canbus.config import CanNetwork


def test_closed_event_values_retain_explicit_input_data() -> None:
    sample = SpeedSample(42.5, 10.0, CanNetwork.FCAN)

    assert ButtonPressed(7).button_index == 7
    assert SpeedObserved(sample).sample is sample
    assert ControlTimerElapsed(11.0).now == 11.0


def test_steering_effect_rejects_out_of_range_assistance() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        SetSteeringAssistance(1.1, SteeringCommandReason.MAXIMUM)


def test_button_led_state_rejects_partial_and_unknown_colours() -> None:
    with pytest.raises(ValueError, match="exactly 16"):
        ButtonLedState((LedColour.OFF,) * 15)
    with pytest.raises(ValueError, match="known LED colours"):
        ButtonLedState((LedColour.OFF,) * 15 + ("off",))  # type: ignore[arg-type]
