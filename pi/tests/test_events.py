from e87canbus.events import (
    ButtonState,
    MflButton,
    MflButtonEvent,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)


def test_mfl_event_construction() -> None:
    event = MflButtonEvent(button=MflButton.VOLUME_UP, state=ButtonState.PRESSED)

    assert event.button is MflButton.VOLUME_UP
    assert event.state is ButtonState.PRESSED


def test_neotrellis_event_construction() -> None:
    event = NeoTrellisButtonEvent(button_index=7, state=ButtonState.RELEASED)

    assert event.button_index == 7
    assert event.state is ButtonState.RELEASED


def test_speed_update_event() -> None:
    event = SpeedUpdateEvent(speed_kph=42.5, source_bus="fcan")

    assert event.speed_kph == 42.5
    assert event.source_bus == "fcan"


def test_steering_mode_values() -> None:
    assert SteeringMode.AUTO.value == "auto"
    assert SteeringMode.MANUAL.value == "manual"

