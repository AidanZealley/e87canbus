from e87canbus.application.controller import ApplicationController
from e87canbus.application.events import (
    ButtonState,
    LedColour,
    NeoTrellisButtonEvent,
    SpeedUpdateEvent,
    SteeringMode,
)


def test_initial_state_is_auto_with_blue_mode_led() -> None:
    controller = ApplicationController()

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert controller.desired_outputs()[0].colour is LedColour.BLUE


def test_button_zero_press_toggles_steering_mode_and_led() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert outputs[0].button_index == 0
    assert outputs[0].colour is LedColour.AMBER


def test_button_zero_release_does_not_change_mode() -> None:
    controller = ApplicationController()
    controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.RELEASED))

    assert controller.snapshot().steering_mode is SteeringMode.MANUAL
    assert outputs == ()


def test_second_button_zero_press_returns_to_auto() -> None:
    controller = ApplicationController()
    controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    outputs = controller.handle_event(NeoTrellisButtonEvent(0, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert outputs[0].colour is LedColour.BLUE


def test_unmapped_button_does_not_change_application_state() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(NeoTrellisButtonEvent(1, ButtonState.PRESSED))

    assert controller.snapshot().steering_mode is SteeringMode.AUTO
    assert outputs == ()


def test_speed_event_updates_application_state_without_hardware_output() -> None:
    controller = ApplicationController()

    outputs = controller.handle_event(SpeedUpdateEvent(42.5, "simulated-vehicle"))

    assert controller.snapshot().vehicle_speed_kph == 42.5
    assert outputs == ()
