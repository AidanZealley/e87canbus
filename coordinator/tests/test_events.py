from e87canbus.application.events import ButtonPressed, ControlTimerElapsed, SpeedObserved
from e87canbus.application.state import SpeedSample
from e87canbus.config import CanNetwork


def test_closed_event_values_retain_explicit_input_data() -> None:
    sample = SpeedSample(42.5, 10.0, CanNetwork.FCAN)

    assert ButtonPressed(7).button_index == 7
    assert SpeedObserved(sample).sample is sample
    assert ControlTimerElapsed(11.0).now == 11.0
