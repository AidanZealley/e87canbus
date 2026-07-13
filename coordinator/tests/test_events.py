from e87canbus.application.events import (
    ButtonState,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)
from e87canbus.config import CanNetwork


def test_neotrellis_event_construction() -> None:
    event = NeoTrellisButtonEvent(button_index=7, state=ButtonState.RELEASED)

    assert event.button_index == 7
    assert event.state is ButtonState.RELEASED


def test_speed_update_event() -> None:
    event = SpeedUpdateEvent(speed_kph=42.5, source_network=CanNetwork.FCAN)

    assert event.speed_kph == 42.5
    assert event.source_network is CanNetwork.FCAN


def test_steering_mode_values() -> None:
    assert SteeringMode.AUTO.value == "auto"
    assert SteeringMode.MANUAL.value == "manual"
